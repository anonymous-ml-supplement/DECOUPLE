#!/usr/bin/env python3

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

PROJECT = "DECOUPLE"
STAGE = "STEP2B_MATH_GENPRM"
MODEL_ID = "GenPRM/GenPRM-7B"
EXPECTED = 343

SYSTEM_PROMPT = (
    "You are a math teacher. Your task is to review and critique "
    "the paragraphs in solution step by step."
)

FORBIDDEN_KEYS = {
    "possible_answer",
    "ground_truth",
    "path",
    "missed_function",
    "excluded_function",
    "correctness",
    "reward",
    "outcome",
    "oracle",
    "intervention_gain",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg):
    raise RuntimeError(msg)


def check_forbidden(obj, where="root"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in FORBIDDEN_KEYS:
                fail(f"POSTHOC/FORBIDDEN KEY FOUND at {where}: {k}")
            check_forbidden(v, f"{where}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_forbidden(v, f"{where}[{i}]")


def load_json_or_jsonl(path):
    p = Path(path)
    text = p.read_text(encoding="utf-8").strip()

    if not text:
        fail(f"Empty input: {path}")

    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj
        return [obj]
    except json.JSONDecodeError:
        rows = []
        for ln, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception as e:
                fail(f"JSONL parse failure {path}:{ln}: {e}")
        return rows


def find_math_prefix_files(root):
    root = Path(root)
    files = sorted(root.rglob("*.jsonl")) + sorted(root.rglob("*.json"))

    out = []
    for p in files:
        s = str(p).lower()
        if "math" in s and "post" not in s:
            out.append(p)

    if not out:
        fail(f"No Math prefix files found under {root}")

    return out


def extract_problem_and_steps(row):
    history = row.get("history_before_step")
    candidate = row.get("candidate_step")

    if not isinstance(history, list):
        fail(
            f"history_before_step missing for "
            f"{row.get('instance_id')} step {row.get('step_index')}"
        )

    problem = None
    previous_steps = []

    for item in history:
        if not isinstance(item, dict):
            continue

        typ = item.get("type")
        content = item.get("content")

        if typ == "problem" and isinstance(content, str):
            problem = content.strip()
        elif isinstance(content, str) and content.strip():
            previous_steps.append(content.strip())

        txt = item.get("text")
        if typ != "problem" and isinstance(txt, str) and txt.strip():
            previous_steps.append(txt.strip())

    if not problem:
        fail(
            f"Problem text unresolved for "
            f"{row.get('instance_id')} step {row.get('step_index')}"
        )

    if not isinstance(candidate, dict):
        fail(
            f"candidate_step missing for "
            f"{row.get('instance_id')} step {row.get('step_index')}"
        )

    current = candidate.get("text")
    if not isinstance(current, str) or not current.strip():
        fail(
            f"candidate_step.text missing for "
            f"{row.get('instance_id')} step {row.get('step_index')}"
        )

    current = current.strip()

    solution_parts = previous_steps + [current]
    solution_text = "\n".join(solution_parts)

    return problem, solution_text


def reward_to_float(reward):
    if isinstance(reward, (int, float)):
        val = float(reward)

    elif isinstance(reward, (list, tuple)):
        if len(reward) == 0:
            fail("Official GenPRM reward is empty.")

        tail = reward[-1]

        if isinstance(tail, (int, float)):
            val = float(tail)
        elif isinstance(tail, (list, tuple)) and len(tail) > 0:
            val = float(tail[-1])
        else:
            fail(f"Unsupported official reward structure: {type(tail)}")

    else:
        try:
            val = float(reward)
        except Exception:
            fail(f"Unsupported official reward type: {type(reward)}")

    if not math.isfinite(val):
        fail(f"Non-finite official GenPRM reward: {val}")

    return val


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--model", default=MODEL_ID)
    args = parser.parse_args()

    repo_src = Path(
        "10_PILOT/STEP2/02_INPUTS/RAW_AUTHORITY/"
        "GENPRM_REFERENCE/GenPRM/src"
    ).resolve()

    if not repo_src.exists():
        fail(f"Official GenPRM source missing: {repo_src}")

    sys.path.insert(0, str(repo_src))

    from prm_evaluation.genprm_inference import GenPRM, CodeExecutor

    print(f"PROJECT={PROJECT}", flush=True)
    print(f"STAGE={STAGE}", flush=True)
    print(f"MODEL={args.model}", flush=True)
    print(f"EXPECTED_CANDIDATES={EXPECTED}", flush=True)
    print("POSTHOC_ACCESS=NO", flush=True)
    print("TERRA_CALLS=0", flush=True)

    files = find_math_prefix_files(args.prefix_root)

    rows = []

    for p in files:
        for row in load_json_or_jsonl(p):
            if not isinstance(row, dict):
                continue

            benchmark = str(row.get("benchmark", "")).lower()
            kind = str(row.get("candidate_kind", "")).lower()

            if "math" not in benchmark and "math" not in kind:
                continue

            check_forbidden(row)

            rows.append((p, row))

    rows.sort(
        key=lambda x: (
            str(x[1].get("instance_id", "")),
            int(x[1].get("step_index", x[1].get("step", 0))),
        )
    )

    if len(rows) != EXPECTED:
        fail(f"Candidate count mismatch: expected {EXPECTED}, got {len(rows)}")

    print(f"CANDIDATE_COUNT={len(rows)}", flush=True)

    genprm = GenPRM(
        args.model,
        tensor_parallel_size=1,
    )
    code_executor = CodeExecutor()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    score_min = None
    score_max = None

    with output_path.open("w", encoding="utf-8") as fout:
        for source_path, row in rows:
            instance_id = row.get("instance_id")
            step_index = int(row.get("step_index", row.get("step", 0)))

            problem, solution_text = extract_problem_and_steps(row)

            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        "Question: "
                        + problem
                        + "\n\n"
                        + solution_text
                    ),
                },
            ]

            model_output, official_reward = genprm.inference(
                messages,
                cur_step=step_index,
                code_executor=code_executor,
            )

            score = reward_to_float(official_reward)

            score_min = score if score_min is None else min(score_min, score)
            score_max = score if score_max is None else max(score_max, score)

            rec = {
                "project": PROJECT,
                "stage": STAGE,
                "benchmark": row.get("benchmark"),
                "instance_id": instance_id,
                "step_index": step_index,
                "candidate_kind": row.get("candidate_kind"),
                "prefix_hash": row.get("prefix_hash"),
                "model_id": args.model,
                "official_genprm_reward": score,
                "step_prm_score": score,
                "risk_score": 1.0 - score,
                "official_interface": "GenPRM.inference",
                "official_reward_extraction": "GenPRM.get_reward_score",
                "posthoc_access": False,
                "terra_calls": 0,
            }

            fout.write(json.dumps(rec, sort_keys=True) + "\n")
            fout.flush()

            count += 1

            if count % 10 == 0 or count == EXPECTED:
                print(
                    f"PROGRESS={count}/{EXPECTED}",
                    flush=True,
                )

    if count != EXPECTED:
        fail(f"Output row count mismatch: {count}")

    audit = {
        "project": PROJECT,
        "stage": STAGE,
        "status": "PASS",
        "model_id": args.model,
        "candidate_count": count,
        "expected_candidate_count": EXPECTED,
        "score_finite": True,
        "score_min": score_min,
        "score_max": score_max,
        "posthoc_access": False,
        "terra_calls": 0,
        "official_interface": "GenPRM.inference",
        "official_reward_extraction": "GenPRM.get_reward_score",
        "output_sha256": sha256_file(output_path),
    }

    audit_path = Path(args.audit)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"SCORE_MIN={score_min}", flush=True)
    print(f"SCORE_MAX={score_max}", flush=True)
    print("POSTHOC_ACCESS=NO", flush=True)
    print("TERRA_CALLS=0", flush=True)
    print("STATUS=PASS", flush=True)


if __name__ == "__main__":
    main()
