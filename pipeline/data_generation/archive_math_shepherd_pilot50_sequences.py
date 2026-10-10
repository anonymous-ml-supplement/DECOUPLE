#!/usr/bin/env python3

import hashlib
import json
import re
from pathlib import Path


ROOT = Path("__DECOUPLE_ROOT__")

PRE_PATH = (
    ROOT
    / "10_PILOT/STEP1/02_INPUTS/PRE_ONLY/MATH_PILOT50_PRE.jsonl"
)

OUT_DIR = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/STEP1B_TRAJECTORY/ARCHIVED_BASE/MATH_SHEPHERD"
)

AUDIT_DIR = (
    ROOT
    / "10_PILOT/STEP1/06_AUDIT/STEP1B_TRAJECTORY/ARCHIVED_BASE/MATH_SHEPHERD"
)

EXPECTED_RAW_AUTHORITY_SHA256 = (
    "bbe67ca2e1d551734e100297349779b597ddfa9fd7655364ea1f99cc23beb4b6"
)

FORBIDDEN_KEYS = {
    "label",
    "labels",
    "correct",
    "correctness",
    "reward",
    "episode_reward",
    "final_reward",
    "outcome",
    "success",
    "ground_truth",
    "gold_answer",
    "self_repair",
    "repair_label",
    "oracle",
    "oracle_rank",
    "intervention_gain",
    "realized_gain",
    "future_observation",
    "next_observation",
    "post_state",
    "verified_outcome",
    "unchecked_outcome",
    "terminal_reward",
    "terminal_success",
}

STEP_PATTERN = re.compile(
    r"(?=Step\s+\d+\s*:)",
    flags=re.IGNORECASE,
)


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(block)

    return h.hexdigest()


def canonical_json_bytes(obj):
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def recursive_forbidden_keys(obj):
    found = []

    def walk(value, prefix=""):
        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key)
                path = (
                    f"{prefix}.{key_text}"
                    if prefix
                    else key_text
                )

                if key_text.lower() in FORBIDDEN_KEYS:
                    found.append(path)

                walk(child, path)

        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(
                    child,
                    f"{prefix}[{i}]",
                )

    walk(obj)

    return found


def split_problem_and_steps(text):
    match = re.search(
        r"Step\s+1\s*:",
        text,
        flags=re.IGNORECASE,
    )

    if match is None:
        raise RuntimeError(
            "Released Step 1 segmentation marker not found."
        )

    problem = text[:match.start()].strip()
    steps_block = text[match.start():].strip()

    segments = [
        item.strip()
        for item in STEP_PATTERN.split(
            steps_block
        )
        if item.strip()
    ]

    if not segments:
        raise RuntimeError(
            "No released step segments recovered."
        )

    parsed_steps = []

    for expected_index, segment in enumerate(
        segments,
        start=1,
    ):
        header = re.match(
            r"Step\s+(\d+)\s*:",
            segment,
            flags=re.IGNORECASE,
        )

        if header is None:
            raise RuntimeError(
                "Malformed released step segment."
            )

        actual_index = int(
            header.group(1)
        )

        if actual_index != expected_index:
            raise RuntimeError(
                "Non-consecutive released step indices: "
                f"expected={expected_index}, "
                f"actual={actual_index}"
            )

        parsed_steps.append(
            {
                "step_index":
                    actual_index,
                "step_text_raw":
                    segment,
                "step_hash":
                    hashlib.sha256(
                        segment.encode(
                            "utf-8"
                        )
                    ).hexdigest(),
            }
        )

    return problem, parsed_steps


def main():
    rows = []

    with PRE_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            if line.strip():
                rows.append(
                    json.loads(line)
                )

    if len(rows) != 50:
        raise RuntimeError(
            f"Expected 50 PRE rows, got {len(rows)}"
        )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    instance_ids = [
        row["instance_id"]
        for row in rows
    ]

    if len(set(instance_ids)) != 50:
        raise RuntimeError(
            "Math Pilot instance IDs are not unique."
        )

    index = []
    total_steps = 0

    for position, row in enumerate(
        rows,
        start=1,
    ):
        forbidden = recursive_forbidden_keys(
            row
        )

        if forbidden:
            raise RuntimeError(
                "Forbidden PRE keys found: "
                + repr(forbidden)
            )

        problem, steps = (
            split_problem_and_steps(
                row["input"]
            )
        )

        total_steps += len(steps)

        archive = {
            "project":
                "DECOUPLE",
            "stage":
                "10_PILOT",
            "step":
                "STEP1",
            "artifact_type":
                "archived_base_reasoning_sequence",
            "benchmark":
                "Math-Shepherd",
            "instance_id":
                row["instance_id"],
            "task":
                row["task"],
            "selection_hash":
                row["selection_hash"],
            "source_dataset":
                row["source_dataset"],
            "source_file":
                row["source_file"],
            "source_revision":
                row["source_revision"],
            "source_row_id":
                row["source_row_id"],
            "problem_text":
                problem,
            "released_sequence_text":
                row["input"],
            "steps":
                steps,
            "step_count":
                len(steps),
            "observations":
                [],
            "pure_text_reasoning":
                True,
            "model_calls":
                0,
            "posthoc_annotations_opened":
                False,
        }

        canonical_hash = (
            hashlib.sha256(
                canonical_json_bytes(
                    archive
                )
            ).hexdigest()
        )

        archive[
            "canonical_sequence_hash"
        ] = canonical_hash

        output_path = (
            OUT_DIR
            / (
                f"{position:03d}_"
                f"{row['instance_id']}.json"
            )
        )

        output_path.write_text(
            json.dumps(
                archive,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        index.append(
            {
                "position":
                    position,
                "instance_id":
                    row["instance_id"],
                "task":
                    row["task"],
                "source_row_id":
                    row["source_row_id"],
                "selection_hash":
                    row["selection_hash"],
                "step_count":
                    len(steps),
                "canonical_sequence_hash":
                    canonical_hash,
                "archive_path":
                    str(
                        output_path.relative_to(
                            ROOT
                        )
                    ),
                "archive_sha256":
                    sha256_file(
                        output_path
                    ),
            }
        )

        print(
            f"DONE {position}/50 "
            f"{row['instance_id']} "
            f"steps={len(steps)}"
        )

    index_path = (
        OUT_DIR
        / "MATH_SHEPHERD_PILOT50_SEQUENCE_INDEX.json"
    )

    index_path.write_text(
        json.dumps(
            index,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "status":
            "PASS",
        "benchmark":
            "Math-Shepherd",
        "archive_type":
            "released_reasoning_sequences",
        "instance_count":
            50,
        "total_released_steps":
            total_steps,
        "pre_path":
            str(
                PRE_PATH.relative_to(
                    ROOT
                )
            ),
        "pre_sha256":
            sha256_file(
                PRE_PATH
            ),
        "raw_authority_sha256":
            EXPECTED_RAW_AUTHORITY_SHA256,
        "source_revision_matches_raw_authority":
            all(
                row["source_revision"]
                == EXPECTED_RAW_AUTHORITY_SHA256
                for row in rows
            ),
        "released_step_segmentation_used":
            True,
        "model_calls":
            0,
        "posthoc_annotations_opened":
            False,
        "correctness_annotations_used":
            False,
        "trajectory_index_sha256":
            sha256_file(
                index_path
            ),
    }

    if not manifest[
        "source_revision_matches_raw_authority"
    ]:
        raise RuntimeError(
            "Math source revision mismatch."
        )

    manifest_path = (
        AUDIT_DIR
        / "MATH_SHEPHERD_PILOT50_ARCHIVE_MANIFEST.json"
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "===== MATH-SHEPHERD PILOT50 ARCHIVE ====="
    )
    print("STATUS=PASS")
    print("INSTANCE_COUNT=50")
    print(
        f"TOTAL_RELEASED_STEPS={total_steps}"
    )
    print("MODEL_CALLS=0")
    print(
        "POSTHOC_ANNOTATIONS_OPENED=NO"
    )
    print(
        "CORRECTNESS_ANNOTATIONS_USED=NO"
    )
    print(
        "INDEX_SHA256="
        + sha256_file(
            index_path
        )
    )
    print(
        "MANIFEST_SHA256="
        + sha256_file(
            manifest_path
        )
    )


if __name__ == "__main__":
    main()
