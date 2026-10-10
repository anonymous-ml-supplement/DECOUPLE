#!/usr/bin/env python3

import argparse
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys
from pathlib import Path

EXPECTED = 343
FROZEN_PARTIAL_ROWS = 291

EXPECTED_SCORER_SHA256 = (
    "e3e1406f5f545d7805d97be0f4d32bbc3fe24d79aa764e3be8fbf02ccfc47697"
)

EXPECTED_PARTIAL_SHA256 = (
    "8c2059482f24ae620b66303afccb691750383fbcbbfabaefbed65159b63d944f"
)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg):
    raise RuntimeError(msg)


def load_jsonl(path):
    rows = []
    with Path(path).open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                fail(f"JSONL parse failure {path}:{ln}: {exc}")
    return rows


def key_from_input(row):
    return (
        str(row.get("instance_id", "")),
        int(row.get("step_index", row.get("step", 0))),
        str(row.get("prefix_hash", "")),
    )


def key_from_output(row):
    return (
        str(row.get("instance_id", "")),
        int(row.get("step_index", 0)),
        str(row.get("prefix_hash", "")),
    )


def validate_existing(existing, input_rows, minimum_rows):
    if len(existing) < minimum_rows:
        fail(
            f"Existing work shorter than frozen partial: "
            f"{len(existing)} < {minimum_rows}"
        )

    if len(existing) > EXPECTED:
        fail(f"Existing work too long: {len(existing)} > {EXPECTED}")

    seen = set()

    for idx, rec in enumerate(existing):
        k_out = key_from_output(rec)
        k_in = key_from_input(input_rows[idx][1])

        if k_out != k_in:
            fail(
                f"Existing/input sequence mismatch at row {idx + 1}: "
                f"output={k_out} input={k_in}"
            )

        if k_out in seen:
            fail(f"Duplicate existing candidate key: {k_out}")

        seen.add(k_out)

        score = float(rec["step_prm_score"])
        if not math.isfinite(score):
            fail(f"Non-finite existing score at row {idx + 1}")

        if rec.get("posthoc_access") is not False:
            fail(f"POSTHOC flag invalid at row {idx + 1}")

        if int(rec.get("terra_calls", -1)) != 0:
            fail(f"Terra-call flag invalid at row {idx + 1}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix-root", required=True)
    parser.add_argument("--partial", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--scorer", required=True)
    args = parser.parse_args()

    scorer_path = Path(args.scorer).resolve()
    partial_path = Path(args.partial).resolve()
    work_path = Path(args.work).resolve()
    output_path = Path(args.output).resolve()
    audit_path = Path(args.audit).resolve()

    scorer_sha = sha256_file(scorer_path)
    partial_sha = sha256_file(partial_path)

    if scorer_sha != EXPECTED_SCORER_SHA256:
        fail(
            f"Frozen scorer SHA256 mismatch: "
            f"{scorer_sha} != {EXPECTED_SCORER_SHA256}"
        )

    if partial_sha != EXPECTED_PARTIAL_SHA256:
        fail(
            f"Frozen partial SHA256 mismatch: "
            f"{partial_sha} != {EXPECTED_PARTIAL_SHA256}"
        )

    frozen_partial = load_jsonl(partial_path)

    if len(frozen_partial) != FROZEN_PARTIAL_ROWS:
        fail(
            f"Frozen partial row mismatch: "
            f"{len(frozen_partial)} != {FROZEN_PARTIAL_ROWS}"
        )

    spec = importlib.util.spec_from_file_location(
        "frozen_math_genprm_scorer",
        scorer_path,
    )
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)

    repo_src = Path(
        "10_PILOT/STEP2/02_INPUTS/RAW_AUTHORITY/"
        "GENPRM_REFERENCE/GenPRM/src"
    ).resolve()

    if not repo_src.exists():
        fail(f"Official GenPRM source missing: {repo_src}")

    sys.path.insert(0, str(repo_src))

    from prm_evaluation.genprm_inference import GenPRM, CodeExecutor

    files = scorer.find_math_prefix_files(args.prefix_root)

    input_rows = []

    for p in files:
        for row in scorer.load_json_or_jsonl(p):
            if not isinstance(row, dict):
                continue

            benchmark = str(row.get("benchmark", "")).lower()
            kind = str(row.get("candidate_kind", "")).lower()

            if "math" not in benchmark and "math" not in kind:
                continue

            scorer.check_forbidden(row)
            input_rows.append((p, row))

    input_rows.sort(
        key=lambda x: (
            str(x[1].get("instance_id", "")),
            int(x[1].get("step_index", x[1].get("step", 0))),
        )
    )

    if len(input_rows) != EXPECTED:
        fail(
            f"Candidate count mismatch: "
            f"{len(input_rows)} != {EXPECTED}"
        )

    input_keys = [key_from_input(row) for _, row in input_rows]

    if len(set(input_keys)) != EXPECTED:
        fail("Input candidate keys are not unique.")

    validate_existing(
        frozen_partial,
        input_rows,
        FROZEN_PARTIAL_ROWS,
    )

    work_path.parent.mkdir(parents=True, exist_ok=True)

    if not work_path.exists():
        shutil.copy2(partial_path, work_path)
        print("WORK_INITIALIZED_FROM_FROZEN_PARTIAL=YES", flush=True)
    else:
        print("WORK_INITIALIZED_FROM_FROZEN_PARTIAL=NO", flush=True)

    existing = load_jsonl(work_path)

    validate_existing(
        existing,
        input_rows,
        FROZEN_PARTIAL_ROWS,
    )

    initial_count = len(existing)

    print("PROJECT=DECOUPLE", flush=True)
    print("STAGE=STEP2B3_PRM_AT_BOK_MATH_RESUME", flush=True)
    print(f"MODEL={args.model}", flush=True)
    print(f"FROZEN_SCORER_SHA256={scorer_sha}", flush=True)
    print(f"FROZEN_PARTIAL_SHA256={partial_sha}", flush=True)
    print(f"EXPECTED_CANDIDATES={EXPECTED}", flush=True)
    print(f"RESUME_INITIAL_ROWS={initial_count}", flush=True)
    print(f"RESUME_MISSING_ROWS={EXPECTED - initial_count}", flush=True)
    print("POSTHOC_ACCESS=NO", flush=True)
    print("TERRA_CALLS=0", flush=True)

    if initial_count < EXPECTED:
        next_row = input_rows[initial_count][1]
        print(
            "FIRST_MISSING="
            f"{next_row.get('instance_id')}"
            f":{int(next_row.get('step_index', next_row.get('step', 0)))}"
            f":{next_row.get('prefix_hash')}",
            flush=True,
        )

        genprm = GenPRM(
            args.model,
            tensor_parallel_size=1,
        )
        code_executor = CodeExecutor()

        with work_path.open("a", encoding="utf-8") as fout:
            for idx in range(initial_count, EXPECTED):
                source_path, row = input_rows[idx]

                instance_id = row.get("instance_id")
                step_index = int(
                    row.get("step_index", row.get("step", 0))
                )

                print(
                    f"SCORING_ROW={idx + 1}/{EXPECTED} "
                    f"INSTANCE={instance_id} STEP={step_index}",
                    flush=True,
                )

                problem, solution_text = scorer.extract_problem_and_steps(row)

                messages = [
                    {
                        "role": "system",
                        "content": scorer.SYSTEM_PROMPT,
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

                score = scorer.reward_to_float(official_reward)

                rec = {
                    "project": scorer.PROJECT,
                    "stage": scorer.STAGE,
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
                os.fsync(fout.fileno())

                print(
                    f"RESUME_PROGRESS={idx + 1}/{EXPECTED}",
                    flush=True,
                )

    final_rows = load_jsonl(work_path)

    if len(final_rows) != EXPECTED:
        fail(
            f"Resume incomplete: "
            f"{len(final_rows)} != {EXPECTED}"
        )

    validate_existing(
        final_rows,
        input_rows,
        FROZEN_PARTIAL_ROWS,
    )

    scores = [float(x["step_prm_score"]) for x in final_rows]

    if not all(math.isfinite(x) for x in scores):
        fail("Final work contains non-finite scores.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_output = output_path.with_name(
        output_path.name + ".resume_complete_tmp"
    )

    shutil.copy2(work_path, tmp_output)

    if len(load_jsonl(tmp_output)) != EXPECTED:
        fail("Temporary final output row validation failed.")

    os.replace(tmp_output, output_path)

    final_sha = sha256_file(output_path)
    work_sha = sha256_file(work_path)

    audit = {
        "project": "DECOUPLE",
        "stage": "STEP2B3_PRM_AT_BOK_MATH_RESUME",
        "status": "PASS",
        "origin_timeout_job": "3733588",
        "model_id": args.model,
        "candidate_count": EXPECTED,
        "expected_candidate_count": EXPECTED,
        "frozen_partial_rows": FROZEN_PARTIAL_ROWS,
        "resume_initial_rows": initial_count,
        "new_rows_scored_this_run": EXPECTED - initial_count,
        "frozen_partial_sha256": partial_sha,
        "frozen_scorer_sha256": scorer_sha,
        "work_sha256": work_sha,
        "output_sha256": final_sha,
        "score_finite": True,
        "score_min": min(scores),
        "score_max": max(scores),
        "posthoc_access": False,
        "terra_calls": 0,
        "official_interface": "GenPRM.inference",
        "official_reward_extraction": "GenPRM.get_reward_score",
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "host": os.uname().nodename,
    }

    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"FINAL_ROWS={EXPECTED}", flush=True)
    print(f"NEW_ROWS_SCORED={EXPECTED - initial_count}", flush=True)
    print(f"SCORE_MIN={min(scores)}", flush=True)
    print(f"SCORE_MAX={max(scores)}", flush=True)
    print(f"FINAL_OUTPUT_SHA256={final_sha}", flush=True)
    print(f"WORK_SHA256={work_sha}", flush=True)
    print("POSTHOC_ACCESS=NO", flush=True)
    print("TERRA_CALLS=0", flush=True)
    print("STATUS=PASS", flush=True)


if __name__ == "__main__":
    main()
