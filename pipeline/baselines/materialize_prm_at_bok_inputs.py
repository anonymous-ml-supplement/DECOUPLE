#!/usr/bin/env python3

import argparse
import copy
import hashlib
import json
from pathlib import Path


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
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def forbidden_findings(obj, path="$"):
    out = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                out.append(path + "." + str(key))
            out.extend(forbidden_findings(value, path + "." + str(key)))

    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            out.extend(forbidden_findings(value, f"{path}[{i}]"))

    return out


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def find_prefix_row(prefix_root, benchmark, instance_id, step_index):
    path = prefix_root / benchmark / f"{instance_id}.jsonl"

    if not path.exists():
        raise RuntimeError(f"Missing prefix file: {path}")

    matches = []

    for row in load_jsonl(path):
        si = int(row.get("step_index", row.get("step", -1)))
        if si == int(step_index):
            matches.append(row)

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one prefix row for {benchmark}/{instance_id}/"
            f"{step_index}; got {len(matches)}"
        )

    return matches[0]


def continuation_text(proposal):
    cont = proposal.get("continuation")

    if isinstance(cont, dict):
        for key in ("text", "content", "assistant_text"):
            if isinstance(cont.get(key), str):
                return cont[key]

    for key in ("visible_text", "text"):
        if isinstance(proposal.get(key), str):
            return proposal[key]

    return ""


def bfcl_candidate(proposal):
    typ = proposal.get("continuation_type")

    if typ == "assistant_text":
        return {
            "action_type": "assistant_text",
            "text": continuation_text(proposal),
        }

    if typ == "no_observable_output":
        return {
            "action_type": "assistant_text",
            "text": "",
        }

    if typ in ("tool_call", "joint_tool_call"):
        cont = proposal.get("continuation", {})
        calls = cont.get("function_calls", proposal.get("function_calls", []))

        if not isinstance(calls, list) or not calls:
            raise RuntimeError("BFCL tool proposal missing function_calls")

        mapped = []

        for call in calls:
            mapped.append({
                "arguments": call.get("arguments", {}),
                "function_name": call.get("name", call.get("function_name")),
                "raw_function_call": call.get("raw_function_call"),
                "call_id": call.get("call_id"),
            })

        return {
            "action_type": typ,
            "function_calls": mapped,
            "parallel_call_count": len(mapped),
        }

    raise RuntimeError(f"Unsupported BFCL continuation_type={typ}")


def toolalpaca_candidate(proposal):
    typ = proposal.get("continuation_type")

    if typ == "assistant_text":
        return {
            "action_type": "assistant_text",
            "text": continuation_text(proposal),
        }

    if typ == "no_observable_output":
        return {
            "action_type": "assistant_text",
            "text": "",
        }

    if typ == "tool_call":
        cont = proposal.get("continuation", {})
        calls = cont.get("function_calls", proposal.get("function_calls", []))

        if not isinstance(calls, list) or len(calls) != 1:
            raise RuntimeError(
                "ToolAlpaca tool_call must contain exactly one function call"
            )

        call = calls[0]

        return {
            "action_type": "tool_call",
            "function_name": call.get("name", call.get("function_name")),
            "arguments": call.get("arguments", {}),
            "call_id": call.get("call_id"),
        }

    raise RuntimeError(f"Unsupported ToolAlpaca continuation_type={typ}")


def math_candidate(proposal):
    text = continuation_text(proposal)

    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Math proposal must contain non-empty text")

    return {
        "action_type": "assistant_text",
        "text": text,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    root = Path(args.root)
    out_root = Path(args.output_root)

    prefix_root = (
        root
        / "10_PILOT/STEP1/04_OUTPUTS/STEP1C_PREFIX/CAUSAL_PREFIXES"
    )

    k8_root = (
        root
        / "10_PILOT/STEP1/04_OUTPUTS/STEP1D_SEMANTIC/K8_CONTINUATIONS"
    )

    index_path = k8_root / "PILOT_K8_CONTINUATION_INDEX.json"
    index = json.load(open(index_path, encoding="utf-8"))

    expected_candidates = {
        "BFCL": 228,
        "ToolAlpaca": 60,
        "Math-Shepherd": 343,
    }

    expected_proposals = {
        "BFCL": 1824,
        "ToolAlpaca": 480,
        "Math-Shepherd": 2744,
    }

    candidate_counts = {k: 0 for k in expected_candidates}
    proposal_counts = {k: 0 for k in expected_candidates}

    handles = {}

    for k in range(1, 9):
        for benchmark in expected_candidates:
            d = out_root / f"k{k:02d}" / benchmark
            d.mkdir(parents=True, exist_ok=True)
            handles[(k, benchmark)] = open(
                d / "proposal_prefixes.jsonl",
                "w",
                encoding="utf-8",
            )

    try:
        for item in index:
            benchmark = item["benchmark"]
            instance_id = item["instance_id"]
            step_index = int(item["step_index"])

            if benchmark not in expected_candidates:
                raise RuntimeError(f"Unexpected benchmark: {benchmark}")

            candidate_counts[benchmark] += 1

            source_path = root / item["path"]

            if sha256_file(source_path) != item["sha256"]:
                raise RuntimeError(f"K8 hash mismatch: {source_path}")

            proposals = load_jsonl(source_path)

            if len(proposals) != 8:
                raise RuntimeError(
                    f"Expected K=8 for {source_path}; got {len(proposals)}"
                )

            base = find_prefix_row(
                prefix_root,
                benchmark,
                instance_id,
                step_index,
            )

            if forbidden_findings(base):
                raise RuntimeError(
                    f"Forbidden PRE/POST violation in base prefix "
                    f"{benchmark}/{instance_id}/{step_index}"
                )

            for proposal in proposals:
                k = int(proposal["continuation_index"])

                if proposal.get("posthoc_fields_used") is not False:
                    raise RuntimeError(
                        f"posthoc_fields_used not false: {source_path}"
                    )

                row = copy.deepcopy(base)

                if benchmark == "BFCL":
                    row["candidate_step"] = bfcl_candidate(proposal)

                elif benchmark == "ToolAlpaca":
                    row["candidate_step"] = toolalpaca_candidate(proposal)

                elif benchmark == "Math-Shepherd":
                    row["candidate_step"] = math_candidate(proposal)

                row["candidate_kind"] = proposal.get(
                    "continuation_type",
                    row.get("candidate_kind"),
                )

                row["prm_at_bok_proposal_index"] = k
                row["prm_at_bok_source_k8_sha256"] = item["sha256"]
                row["prm_at_bok_source_path"] = item["path"]
                row["prm_at_bok_posthoc_access"] = False

                if forbidden_findings(row):
                    raise RuntimeError(
                        f"Forbidden field after materialization: "
                        f"{benchmark}/{instance_id}/{step_index}/k{k}"
                    )

                handles[(k, benchmark)].write(
                    json.dumps(
                        row,
                        sort_keys=True,
                        ensure_ascii=False,
                    )
                    + "\n"
                )

                proposal_counts[benchmark] += 1

    finally:
        for f in handles.values():
            f.close()

    if candidate_counts != expected_candidates:
        raise RuntimeError(
            f"Candidate counts mismatch: {candidate_counts}"
        )

    if proposal_counts != expected_proposals:
        raise RuntimeError(
            f"Proposal counts mismatch: {proposal_counts}"
        )

    manifest = {
        "status": "PASS",
        "posthoc_access": False,
        "new_terra_calls": 0,
        "k": 8,
        "candidate_counts": candidate_counts,
        "proposal_counts": proposal_counts,
        "total_candidates": sum(candidate_counts.values()),
        "total_proposals": sum(proposal_counts.values()),
        "k8_index": str(index_path.relative_to(root)),
        "k8_index_sha256": sha256_file(index_path),
    }

    manifest_path = out_root / "PRM_AT_BOK_INPUT_MANIFEST.json"

    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("===== PRM@BoK INPUT MATERIALIZATION =====")
    print("CANDIDATES=631")
    print("TOOL_CANDIDATES=288")
    print("MATH_CANDIDATES=343")
    print("PROPOSALS=5048")
    print("TOOL_PROPOSALS=2304")
    print("MATH_PROPOSALS=2744")
    print("K=8")
    print("POSTHOC_ACCESS=NO")
    print("NEW_TERRA_CALLS=0")
    print("STATUS=PASS")


if __name__ == "__main__":
    main()
