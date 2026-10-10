#!/usr/bin/env python3

import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
import torch
from transformers import AutoTokenizer


ROOT = Path("__DECOUPLE_ROOT__")

PREFIX_ROOT = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1C_PREFIX/CAUSAL_PREFIXES"
)

SKYWORK_REPO = (
    ROOT
    / "10_PILOT/STEP1/02_INPUTS/"
      "RAW_AUTHORITY/"
      "TOOLPRMBENCH_REFERENCE/"
      "ToolPRMBench/third_party/"
      "skywork-o1-prm-inference"
)

OUT_ROOT = (
    ROOT
    / "10_PILOT/STEP2/04_OUTPUTS/"
      "STEP2B_PRM_SCORING/TOOL_PRM"
)

AUDIT_ROOT = (
    ROOT
    / "10_PILOT/STEP2/06_AUDIT/"
      "STEP2B_PRM_SCORING"
)

MODEL_ID = (
    "Skywork/"
    "Skywork-o1-Open-PRM-Qwen-2.5-7B"
)

EXPECTED = {
    "BFCL": 228,
    "ToolAlpaca": 60,
}

FORBIDDEN_KEYS = {
    "possible_answer",
    "ground_truth",
    "correct",
    "correctness",
    "reward",
    "outcome",
    "oracle",
    "intervention_gain",
    "missed_function",
    "excluded_function",
}


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(block)

    return h.hexdigest()


def sha256_tree(root):
    h = hashlib.sha256()

    for path in sorted(
        p for p in root.rglob("*")
        if p.is_file()
    ):
        rel = str(
            path.relative_to(root)
        )

        h.update(
            (
                rel
                + "\t"
                + sha256_file(path)
                + "\n"
            ).encode("utf-8")
        )

    return h.hexdigest()


def nested_forbidden_findings(obj, path="$"):
    findings = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            lk = str(key).lower()

            if lk in FORBIDDEN_KEYS:
                findings.append({
                    "path": path,
                    "key": key,
                })

            findings.extend(
                nested_forbidden_findings(
                    value,
                    path + "." + str(key),
                )
            )

    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            findings.extend(
                nested_forbidden_findings(
                    value,
                    f"{path}[{i}]",
                )
            )

    return findings


def load_domain(domain):
    root = PREFIX_ROOT / domain

    rows = []

    for path in sorted(
        root.glob("*.jsonl")
    ):
        with path.open(
            encoding="utf-8"
        ) as f:
            for line_no, line in enumerate(
                f,
                start=1,
            ):
                if not line.strip():
                    continue

                row = json.loads(line)

                findings = (
                    nested_forbidden_findings(
                        row
                    )
                )

                if findings:
                    raise RuntimeError(
                        "Forbidden POST field in "
                        f"{path}:{line_no}: "
                        f"{findings[:5]}"
                    )

                rows.append(
                    (
                        path,
                        line_no,
                        row,
                    )
                )

    if len(rows) != EXPECTED[domain]:
        raise RuntimeError(
            f"{domain}: expected "
            f"{EXPECTED[domain]}, "
            f"got {len(rows)}"
        )

    return rows


def stringify(value):
    if isinstance(value, str):
        return value

    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
    )


def build_problem(row):
    history = row.get(
        "history_before_step",
        []
    )

    parts = []

    for item in history:
        if not isinstance(item, dict):
            continue

        kind = item.get(
            "kind",
            item.get(
                "role",
                "history",
            ),
        )

        content = None

        for key in (
            "text",
            "content",
            "user_message",
            "observation",
            "tool_observation",
            "tool_result",
        ):
            if key in item:
                content = item[key]
                break

        if content is None:
            content = item

        parts.append(
            f"[{kind}] "
            + stringify(content)
        )

    return (
        "A tool-using agent is solving a task. "
        "Evaluate whether the proposed next "
        "assistant action is an appropriate "
        "intermediate step given only the "
        "interaction history available before "
        "that action.\n\n"
        "Interaction history:\n"
        + "\n".join(parts)
    )


def build_response(row):
    candidate = row.get(
        "candidate_step"
    )

    if not isinstance(candidate, dict):
        raise RuntimeError(
            "candidate_step must be dict"
        )

    if (
        "function_name" in candidate
        or "arguments" in candidate
    ):
        payload = {
            "function_name":
                candidate.get(
                    "function_name"
                ),
            "arguments":
                candidate.get(
                    "arguments"
                ),
        }

        return json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
        )

    for key in (
        "text",
        "assistant_text",
        "content",
    ):
        if isinstance(
            candidate.get(key),
            str,
        ):
            return candidate[key]

    return json.dumps(
        candidate,
        sort_keys=True,
        ensure_ascii=False,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        default=MODEL_ID,
    )

    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA_REQUIRED_FOR_FORMAL_PRM_RUN"
        )

    if str(SKYWORK_REPO) not in sys.path:
        sys.path.insert(
            0,
            str(SKYWORK_REPO),
        )

    from model_utils.prm_model import (
        PRM_MODEL,
    )

    from model_utils.io_utils import (
        prepare_input,
        prepare_batch_input_for_model,
        derive_step_rewards,
    )

    tokenizer = (
        AutoTokenizer.from_pretrained(
            args.model,
            trust_remote_code=True,
        )
    )

    model = PRM_MODEL.from_pretrained(
        args.model,
        device_map="auto",
    ).eval()

    OUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_output_rows = []

    counts = {}

    for domain in (
        "BFCL",
        "ToolAlpaca",
    ):
        rows = load_domain(
            domain
        )

        counts[domain] = len(rows)

        for idx, (
            source_path,
            line_no,
            row,
        ) in enumerate(
            rows,
            start=1,
        ):
            problem = build_problem(
                row
            )

            response = build_response(
                row
            )

            (
                input_ids,
                _steps,
                reward_flags,
            ) = prepare_input(
                problem,
                response,
                tokenizer=tokenizer,
                step_token="\n",
            )

            (
                batch_ids,
                attention_mask,
                batch_flags,
            ) = (
                prepare_batch_input_for_model(
                    [input_ids],
                    [reward_flags],
                    tokenizer.pad_token_id,
                )
            )

            device = next(
                model.parameters()
            ).device

            with torch.no_grad():
                _, _, rewards = model(
                    input_ids=batch_ids.to(
                        device
                    ),
                    attention_mask=(
                        attention_mask.to(
                            device
                        )
                    ),
                    return_probs=True,
                )

            step_rewards = (
                derive_step_rewards(
                    rewards,
                    batch_flags,
                )[0]
            )

            if not step_rewards:
                score = 0.0
            else:
                score = float(
                    np.mean(
                        step_rewards
                    )
                )

            if not math.isfinite(score):
                raise RuntimeError(
                    "Non-finite tool PRM score."
                )

            if not (
                0.0 <= score <= 1.0
            ):
                raise RuntimeError(
                    f"Score out of range: {score}"
                )

            all_output_rows.append({
                "benchmark":
                    domain,
                "instance_id":
                    row["instance_id"],
                "step_index":
                    int(
                        row["step_index"]
                    ),
                "prefix_hash":
                    row["prefix_hash"],
                "candidate_kind":
                    row["candidate_kind"],
                "model_id":
                    args.model,
                "baseline":
                    "Tool-Step-PRM",
                "process_correctness_score":
                    score,
                "risk_score":
                    1.0 - score,
                "step_rewards":
                    [
                        float(x)
                        for x
                        in step_rewards
                    ],
                "source_prefix_file":
                    str(
                        source_path.relative_to(
                            ROOT
                        )
                    ),
                "source_line":
                    line_no,
                "posthoc_access":
                    False,
            })

            if (
                idx == 1
                or idx % 25 == 0
                or idx == len(rows)
            ):
                print(
                    f"DOMAIN={domain} "
                    f"PROGRESS={idx}/"
                    f"{len(rows)}",
                    flush=True,
                )

    if len(all_output_rows) != 288:
        raise RuntimeError(
            "Expected 288 tool candidates, "
            f"got {len(all_output_rows)}"
        )

    output_path = (
        OUT_ROOT
        / "tool_step_prm_scores.jsonl"
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        for row in all_output_rows:
            f.write(
                json.dumps(
                    row,
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n"
            )

    values = [
        row[
            "process_correctness_score"
        ]
        for row in all_output_rows
    ]

    audit = {
        "status":
            "PASS",
        "candidate_count":
            len(all_output_rows),
        "domain_counts":
            counts,
        "model_id":
            args.model,
        "score_interface":
            "mean_step_reward_for_candidate_action",
        "risk_transform":
            "1_minus_process_correctness_score",
        "score_min":
            min(values),
        "score_max":
            max(values),
        "score_mean":
            sum(values)
            / len(values),
        "finite_fraction":
            sum(
                math.isfinite(x)
                for x in values
            )
            / len(values),
        "posthoc_access":
            False,
        "terra_calls":
            0,
        "cuda":
            True,
        "cuda_device":
            torch.cuda.get_device_name(0),
        "torch_version":
            torch.__version__,
        "python_version":
            platform.python_version(),
        "prefix_root_sha256":
            sha256_tree(
                PREFIX_ROOT
            ),
        "vendored_skywork_repo_sha256":
            sha256_tree(
                SKYWORK_REPO
            ),
        "output_sha256":
            sha256_file(
                output_path
            ),
    }

    audit_path = (
        AUDIT_ROOT
        / "tool_step_prm_audit.json"
    )

    audit_path.write_text(
        json.dumps(
            audit,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("===== FINAL =====")
    print("BFCL_CANDIDATES=228")
    print("TOOLALPACA_CANDIDATES=60")
    print("TOTAL_CANDIDATES=288")
    print(
        "MODEL="
        + args.model
    )
    print(
        "SCORE_MIN="
        + str(min(values))
    )
    print(
        "SCORE_MAX="
        + str(max(values))
    )
    print("POSTHOC_ACCESS=NO")
    print("TERRA_CALLS=0")
    print("STATUS=PASS")


if __name__ == "__main__":
    main()
