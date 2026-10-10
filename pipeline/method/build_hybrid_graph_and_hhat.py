#!/usr/bin/env python3

import hashlib
import json
import math
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path("__DECOUPLE_ROOT__")

PREFIX_ROOT = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1C_PREFIX/CAUSAL_PREFIXES"
)

PT_PATH = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1D_SEMANTIC/SEMANTIC_CLASSES_PT/"
      "semantic_candidate_scores.jsonl"
)

OUT = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1E_GRAPH/HYBRID_GRAPH_HHAT"
)

ALPHA_CONFIG = (
    ROOT
    / "15_DEV_FREEZE/config/"
      "structural_harm_alpha.json"
)

ALPHA_RESULT = (
    ROOT
    / "15_DEV_FREEZE/results/"
      "structural_harm_alpha_freeze.json"
)

ALPHA_MANIFEST = (
    ROOT
    / "15_DEV_FREEZE/manifests/"
      "structural_harm_alpha_manifest.json"
)

WINDOW = 3
SPARSE_EXPLICIT_LINK_THRESHOLD = 2

EXPECTED_CANDIDATES = 631
EXPECTED_BENCHMARK_COUNTS = {
    "BFCL": 228,
    "Math-Shepherd": 343,
    "ToolAlpaca": 60,
}

OUT_NODES = OUT / "hybrid_graph_nodes.jsonl"
OUT_EDGES = OUT / "hybrid_graph_edges.jsonl"
OUT_COMPONENTS = OUT / "structural_harm_components.jsonl"
OUT_SCORES = OUT / "structural_harm_scores.jsonl"
OUT_AUDIT = OUT / "graph_audit.json"
OUT_COMPUTE = OUT / "compute_ledger.json"
OUT_MANIFEST = OUT / "graph_manifest.json"


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def normalize_text(x):
    x = unicodedata.normalize("NFKC", str(x))
    x = re.sub(r"\s+", " ", x).strip()
    return x


def normalize_scalar(x):
    if isinstance(x, bool):
        return str(x).lower()
    if x is None:
        return "null"
    if isinstance(x, (int, float)):
        return str(x)
    return normalize_text(x).lower()


def flatten_scalars(x):
    out = []

    if isinstance(x, dict):
        for k in sorted(x):
            out.extend(flatten_scalars(x[k]))

    elif isinstance(x, list):
        for v in x:
            out.extend(flatten_scalars(v))

    elif isinstance(x, (str, int, float, bool)) or x is None:
        s = normalize_scalar(x)

        # Ignore trivial punctuation and tiny stop-like values.
        if len(s) >= 2:
            out.append(s)

    return out


def parse_json_if_possible(text):
    try:
        return json.loads(text)
    except Exception:
        return text


def tokens_from_text(text):
    text = normalize_text(text).lower()

    return set(
        re.findall(
            r"[a-zA-Z_][a-zA-Z0-9_.-]*|"
            r"-?\d+(?:\.\d+)?",
            text,
        )
    )


def math_symbols(text):
    text = normalize_text(text)

    # Remove leading "Step N:" so step numbering does not
    # create artificial dependencies.
    text = re.sub(
        r"^\s*Step\s+\d+\s*:\s*",
        "",
        text,
        flags=re.I,
    )

    candidates = set(
        re.findall(
            r"(?<![A-Za-z0-9_])"
            r"[A-Za-z][A-Za-z0-9_]*"
            r"(?![A-Za-z0-9_])"
            r"|"
            r"-?\d+(?:\.\d+)?",
            text,
        )
    )

    stop = {
        "a", "an", "and", "are", "as", "at", "be",
        "by", "for", "from", "he", "her", "if", "in",
        "is", "it", "of", "on", "or", "she", "so",
        "that", "the", "then", "they", "this", "to",
        "two", "was", "we", "were", "with", "x",
        "answer", "step",
    }

    return {
        normalize_text(x).lower()
        for x in candidates
        if normalize_text(x).lower() not in stop
    }


def explicit_step_refs(text):
    refs = set()

    for m in re.finditer(
        r"\b(?:step|equation|eq\.?)\s*(\d+)\b",
        str(text),
        flags=re.I,
    ):
        refs.add(int(m.group(1)))

    return refs


def load_prefixes():
    trajectories = defaultdict(list)
    benchmark_counts = Counter()

    for path in sorted(PREFIX_ROOT.rglob("*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                row = json.loads(line)

                if bool(row.get("posthoc_fields_used", False)):
                    raise RuntimeError(
                        "posthoc_fields_used=True in causal prefix"
                    )

                key = (
                    row["benchmark"],
                    row["instance_id"],
                )

                trajectories[key].append(row)
                benchmark_counts[row["benchmark"]] += 1

    for key, rows in trajectories.items():
        rows.sort(key=lambda r: int(r["step_index"]))

        expected = list(range(1, len(rows) + 1))
        actual = [int(r["step_index"]) for r in rows]

        if actual != expected:
            raise RuntimeError(
                f"Non-contiguous step_index for {key}: {actual}"
            )

    total = sum(len(v) for v in trajectories.values())

    if total != EXPECTED_CANDIDATES:
        raise RuntimeError(
            f"Expected {EXPECTED_CANDIDATES} candidates, got {total}"
        )

    if dict(benchmark_counts) != EXPECTED_BENCHMARK_COUNTS:
        raise RuntimeError(
            "Benchmark count mismatch: "
            + repr(dict(benchmark_counts))
        )

    return trajectories, benchmark_counts


def load_pt_contract():
    records = {}

    with PT_PATH.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            r = json.loads(line)

            key = (
                r["benchmark"],
                r["instance_id"],
                int(r["step_index"]),
            )

            records[key] = r

    if len(records) != EXPECTED_CANDIDATES:
        raise RuntimeError(
            "p_t record count mismatch."
        )

    return records


def prior_observation_values(row):
    values = []

    for event in row.get("history_before_step", []):
        etype = event.get("type")

        if etype == "tool_observation":
            if "contents" in event:
                for raw in event["contents"]:
                    obj = parse_json_if_possible(raw)
                    values.extend(flatten_scalars(obj))

            if "content" in event:
                obj = parse_json_if_possible(event["content"])
                values.extend(flatten_scalars(obj))

    return set(values)


def current_argument_values(row):
    step = row["candidate_step"]

    if row["benchmark"] == "BFCL":
        values = []

        for call in step.get("function_calls", []):
            values.extend(
                flatten_scalars(
                    call.get("arguments", {})
                )
            )

        return set(values)

    if row["benchmark"] == "ToolAlpaca":
        return set(
            flatten_scalars(
                step.get("arguments", {})
            )
        )

    return set()


def current_text(row):
    step = row["candidate_step"]

    if "text" in step:
        return normalize_text(step["text"])

    return ""


def structured_dependency_edges(rows):
    """
    PRE-only deterministic structured dependency rule.

    A prior step i is connected to later step j when:
      1. a scalar value returned in the tool observation
         produced by i appears exactly in arguments of j; or
      2. for a later assistant-text step, nontrivial tokens
         from the prior tool observation reappear in the text.

    This is a conservative observed-consumption rule.
    It does not infer hidden causal state.
    """

    edges = []
    produced_by_step = defaultdict(set)

    # Recover prior observations from each later prefix.
    for row in rows:
        for event in row.get("history_before_step", []):
            if event.get("type") != "tool_observation":
                continue

            src = int(event["step_index"])

            if "contents" in event:
                for raw in event["contents"]:
                    produced_by_step[src].update(
                        flatten_scalars(
                            parse_json_if_possible(raw)
                        )
                    )

            if "content" in event:
                produced_by_step[src].update(
                    flatten_scalars(
                        parse_json_if_possible(
                            event["content"]
                        )
                    )
                )

    for row in rows:
        j = int(row["step_index"])
        args = current_argument_values(row)
        text = current_text(row)
        text_tokens = tokens_from_text(text)

        for i in sorted(produced_by_step):
            if i >= j:
                continue

            produced = produced_by_step[i]

            exact_overlap = sorted(
                produced.intersection(args)
            )

            if exact_overlap:
                edges.append({
                    "source_step": i,
                    "target_step": j,
                    "edge_family": "structured",
                    "edge_type": "tool_return_to_argument",
                    "evidence": exact_overlap[:20],
                })
                continue

            if text:
                prod_tokens = set()

                for value in produced:
                    prod_tokens.update(
                        tokens_from_text(value)
                    )

                overlap = sorted(
                    t
                    for t in prod_tokens.intersection(text_tokens)
                    if len(t) >= 4
                )

                if overlap:
                    edges.append({
                        "source_step": i,
                        "target_step": j,
                        "edge_family": "structured",
                        "edge_type": "tool_return_to_answer_text",
                        "evidence": overlap[:20],
                    })

    return edges


def math_dependency_edges(rows):
    """
    Deterministic mathematical graph.

    Explicit edges:
      - direct Step/Equation reference;
      - normalized symbol reuse.

    If the target step has fewer than two explicit incoming
    symbol/proposition links, add forward co-occurrence edges
    from up to the previous w=3 steps.

    s_sparse is defined from the explicit-link count before
    co-occurrence fallback, exactly as required by spec2.
    """

    edges = []
    explicit_in_count = Counter()

    symbols = {}
    texts = {}

    for row in rows:
        t = int(row["step_index"])
        txt = current_text(row)
        texts[t] = txt
        symbols[t] = math_symbols(txt)

    T = len(rows)

    for j in range(1, T + 1):
        refs = explicit_step_refs(texts[j])

        for i in range(1, j):
            reasons = []

            if i in refs:
                reasons.append("explicit_step_reference")

            shared = sorted(
                symbols[i].intersection(symbols[j])
            )

            if shared:
                reasons.append("normalized_symbol_reuse")

            if reasons:
                explicit_in_count[j] += 1

                edges.append({
                    "source_step": i,
                    "target_step": j,
                    "edge_family": "text",
                    "edge_type": "+".join(reasons),
                    "evidence": shared[:20],
                })

        if explicit_in_count[j] < SPARSE_EXPLICIT_LINK_THRESHOLD:
            start = max(1, j - WINDOW)

            existing_sources = {
                e["source_step"]
                for e in edges
                if e["target_step"] == j
            }

            for i in range(start, j):
                if i in existing_sources:
                    continue

                edges.append({
                    "source_step": i,
                    "target_step": j,
                    "edge_family": "text",
                    "edge_type": "cooccurrence_fallback_w3",
                    "evidence": [],
                })

    sparse = {
        t: int(
            explicit_in_count[t]
            < SPARSE_EXPLICIT_LINK_THRESHOLD
        )
        for t in range(1, T + 1)
    }

    return edges, explicit_in_count, sparse


def add_terminal_sink(edges, T):
    """
    The global final auditable step receives a directed edge
    to an outcome sink. The sink is not assigned an ordinary
    candidate step index, so Eq. 34 is checked on candidate
    edges and terminal sink direction is separately audited.
    """

    edges.append({
        "source_step": T,
        "target_step": None,
        "target_node": "FINAL_OUTCOME_SINK",
        "edge_family": "terminal",
        "edge_type": "terminal_outcome_sink",
        "evidence": [],
    })


def median_positive(values):
    values = [
        float(x)
        for x in values
        if float(x) > 0
    ]

    if not values:
        return None

    return statistics.median(values)


def main():
    print("===== STEP1E HYBRID GRAPH + H_HAT =====")
    print("TEXT_WINDOW=3")
    print("SPARSE_EXPLICIT_LINK_THRESHOLD=2")
    print("POSTHOC_ACCESS=NO")
    print("TERRA_CALLS=0")

    trajectories, benchmark_counts = load_prefixes()
    pt_records = load_pt_contract()

    all_nodes = []
    all_edges = []
    pre_alpha_components = []

    explicit_positive_outdegrees = []
    sparse_positive_depths = []

    for (benchmark, instance_id), rows in sorted(trajectories.items()):
        T = len(rows)

        for row in rows:
            t = int(row["step_index"])

            pt_key = (
                benchmark,
                instance_id,
                t,
            )

            if pt_key not in pt_records:
                raise RuntimeError(
                    "Missing p_t alignment: " + repr(pt_key)
                )

            if (
                pt_records[pt_key]["prefix_hash"]
                != row["prefix_hash"]
            ):
                raise RuntimeError(
                    "Prefix hash mismatch: " + repr(pt_key)
                )

            all_nodes.append({
                "benchmark": benchmark,
                "instance_id": instance_id,
                "node_type": "candidate_step",
                "step_index": t,
                "candidate_kind": row["candidate_kind"],
                "prefix_hash": row["prefix_hash"],
            })

        if benchmark == "Math-Shepherd":
            edges, explicit_in, sparse = math_dependency_edges(rows)
        else:
            edges = structured_dependency_edges(rows)
            explicit_in = Counter()
            sparse = {t: 0 for t in range(1, T + 1)}

        add_terminal_sink(edges, T)

        candidate_out = Counter()

        for e in edges:
            if e.get("target_step") is not None:
                i = int(e["source_step"])
                j = int(e["target_step"])

                if not (i < j):
                    raise RuntimeError(
                        f"DAG violation {benchmark}/{instance_id}: {i}->{j}"
                    )

            candidate_out[int(e["source_step"])] += 1

            record = {
                "benchmark": benchmark,
                "instance_id": instance_id,
                **e,
            }

            all_edges.append(record)

        for t in range(1, T + 1):
            deg_out = int(candidate_out[t])
            s_sparse = int(sparse[t])

            pre_alpha_components.append({
                "benchmark": benchmark,
                "instance_id": instance_id,
                "step_index": t,
                "T": T,
                "Deg_out": deg_out,
                "s_sparse": s_sparse,
                "explicit_in_links":
                    int(explicit_in[t])
                    if benchmark == "Math-Shepherd"
                    else None,
            })

            # Development-only alpha scale statistics.
            if deg_out > 0:
                explicit_positive_outdegrees.append(deg_out)

            if (
                benchmark == "Math-Shepherd"
                and s_sparse == 1
                and (T - t) > 0
            ):
                sparse_positive_depths.append(T - t)

    # Development-only outcome-blind scale matching.
    #
    # This is an operationalization because spec2 fixes the
    # existence and dev-freeze of alpha but does not specify
    # the selection objective.
    median_degree = median_positive(
        explicit_positive_outdegrees
    )

    median_sparse_depth = median_positive(
        sparse_positive_depths
    )

    if median_degree is None:
        raise RuntimeError(
            "Cannot freeze alpha: no positive out-degree."
        )

    if median_sparse_depth is None:
        alpha = 0.0
        alpha_reason = (
            "No positive remaining-depth sparse Math step "
            "in Pilot development data."
        )
    else:
        alpha = (
            median_degree
            / median_sparse_depth
        )
        alpha_reason = (
            "Pilot PRE-only scale matching: "
            "median positive observed out-degree divided by "
            "median positive remaining depth among sparse "
            "Math steps."
        )

    if not math.isfinite(alpha) or alpha < 0:
        raise RuntimeError(
            "Invalid frozen alpha."
        )

    print("ALPHA=" + repr(alpha))
    print("ALPHA_SELECTION=PRE_ONLY_SCALE_MATCHING")

    OUT.mkdir(parents=True, exist_ok=True)
    ALPHA_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    ALPHA_RESULT.parent.mkdir(parents=True, exist_ok=True)
    ALPHA_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    alpha_config = {
        "status": "FROZEN",
        "parameter": "alpha",
        "value": alpha,
        "development_stage": "10_PILOT",
        "outcome_blind": True,
        "posthoc_access": False,
        "selection_rule":
            "median_positive_outdegree/"
            "median_positive_sparse_remaining_depth",
        "selection_rationale": alpha_reason,
        "median_positive_outdegree": median_degree,
        "median_positive_sparse_remaining_depth":
            median_sparse_depth,
        "spec_status":
            "pilot_operationalization_of_under_specified_dev_freeze",
    }

    ALPHA_CONFIG.write_text(
        json.dumps(alpha_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    ALPHA_RESULT.write_text(
        json.dumps(alpha_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    alpha_manifest = {
        "status": "FROZEN",
        "alpha": alpha,
        "source": "Pilot PRE graph statistics only",
        "posthoc_access": False,
        "outcomes_used": False,
        "correctness_used": False,
        "intervention_gain_used": False,
        "oracle_used": False,
    }

    ALPHA_MANIFEST.write_text(
        json.dumps(alpha_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    score_records = []
    h_values = []

    for comp in pre_alpha_components:
        t = comp["step_index"]
        T = comp["T"]
        deg = comp["Deg_out"]
        sparse = comp["s_sparse"]

        h_hat = math.log(
            1.0
            + deg
            + alpha * (T - t) * sparse
        )

        if not math.isfinite(h_hat):
            raise RuntimeError("Non-finite H_hat.")

        rec = {
            **comp,
            "alpha": alpha,
            "H_hat": h_hat,
        }

        score_records.append(rec)
        h_values.append(h_hat)

    all_nodes.sort(
        key=lambda r: (
            r["benchmark"],
            r["instance_id"],
            r["step_index"],
        )
    )

    all_edges.sort(
        key=lambda r: (
            r["benchmark"],
            r["instance_id"],
            r["source_step"],
            (
                r["target_step"]
                if r.get("target_step") is not None
                else 10**9
            ),
            r["edge_type"],
        )
    )

    score_records.sort(
        key=lambda r: (
            r["benchmark"],
            r["instance_id"],
            r["step_index"],
        )
    )

    def write_jsonl(path, rows):
        with path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(
                    json.dumps(
                        r,
                        sort_keys=True,
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    write_jsonl(OUT_NODES, all_nodes)
    write_jsonl(OUT_EDGES, all_edges)
    write_jsonl(OUT_COMPONENTS, pre_alpha_components)
    write_jsonl(OUT_SCORES, score_records)

    candidate_edges = [
        e
        for e in all_edges
        if e.get("target_step") is not None
    ]

    dag_violations = sum(
        not (
            int(e["source_step"])
            < int(e["target_step"])
        )
        for e in candidate_edges
    )

    structured_sparse_nonzero = sum(
        r["s_sparse"] != 0
        for r in score_records
        if r["benchmark"] != "Math-Shepherd"
    )

    terminal_sink_count = sum(
        e["edge_type"] == "terminal_outcome_sink"
        for e in all_edges
    )

    audit = {
        "status": "PASS",
        "trajectory_count": len(trajectories),
        "candidate_count": len(score_records),
        "benchmark_candidate_counts":
            dict(sorted(benchmark_counts.items())),
        "edge_count": len(all_edges),
        "candidate_edge_count": len(candidate_edges),
        "terminal_sink_edge_count": terminal_sink_count,
        "all_candidate_edges_forward":
            dag_violations == 0,
        "dag_violations": dag_violations,
        "text_window": WINDOW,
        "sparse_explicit_link_threshold":
            SPARSE_EXPLICIT_LINK_THRESHOLD,
        "structured_sparse_nonzero":
            structured_sparse_nonzero,
        "alpha": alpha,
        "H_hat_finite_rate":
            sum(math.isfinite(x) for x in h_values)
            / len(h_values),
        "H_hat_min": min(h_values),
        "H_hat_max": max(h_values),
        "posthoc_access": False,
        "terra_calls": 0,
    }

    if len(score_records) != EXPECTED_CANDIDATES:
        raise RuntimeError("Candidate output mismatch.")

    if dag_violations != 0:
        raise RuntimeError("DAG violation.")

    if structured_sparse_nonzero != 0:
        raise RuntimeError(
            "Structured-domain sparse flag must be zero."
        )

    if terminal_sink_count != len(trajectories):
        raise RuntimeError(
            "Expected one final outcome sink per trajectory."
        )

    if audit["H_hat_finite_rate"] != 1.0:
        raise RuntimeError("Non-finite H_hat.")

    OUT_AUDIT.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    compute = {
        "status": "PASS",
        "external_api_calls": 0,
        "terra_calls": 0,
        "graph_parser": "deterministic_local_python",
        "candidate_count": EXPECTED_CANDIDATES,
    }

    OUT_COMPUTE.write_text(
        json.dumps(compute, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "status": "FROZEN",
        "stage": "STEP1E_HYBRID_GRAPH_HHAT",
        "spec_mapping": [
            "Eq33_hybrid_graph",
            "Eq34_forward_DAG",
            "Eq35_out_degree",
            "Eq36_structural_harm",
        ],
        "parser_contract": {
            "text_window": WINDOW,
            "sparse_explicit_link_threshold":
                SPARSE_EXPLICIT_LINK_THRESHOLD,
            "math_explicit_links": [
                "direct_step_or_equation_reference",
                "normalized_symbol_reuse",
            ],
            "math_fallback":
                "forward_cooccurrence_previous_up_to_3_steps",
            "structured_dependency":
                "observed_tool_return_consumption_only",
            "structured_sparse_flag": 0,
            "terminal_outcome_sink":
                "global_final_candidate",
        },
        "alpha": {
            "value": alpha,
            "config_path":
                str(ALPHA_CONFIG.relative_to(ROOT)),
            "config_sha256":
                sha256_file(ALPHA_CONFIG),
            "selection":
                "Pilot PRE-only scale matching",
            "posthoc_access": False,
        },
        "inputs": {
            "causal_prefix_root":
                str(PREFIX_ROOT.relative_to(ROOT)),
            "p_t_path":
                str(PT_PATH.relative_to(ROOT)),
            "p_t_sha256":
                sha256_file(PT_PATH),
        },
        "outputs": {
            "nodes_sha256":
                sha256_file(OUT_NODES),
            "edges_sha256":
                sha256_file(OUT_EDGES),
            "components_sha256":
                sha256_file(OUT_COMPONENTS),
            "scores_sha256":
                sha256_file(OUT_SCORES),
            "audit_sha256":
                sha256_file(OUT_AUDIT),
            "compute_sha256":
                sha256_file(OUT_COMPUTE),
        },
        "implementation_sha256":
            sha256_file(Path(__file__).resolve()),
        "posthoc_access": False,
        "terra_calls": 0,
        "next":
            "SIGNAL_AVAILABILITY_GATES_AND_DECOUPLE_PRE_SCORE",
    }

    OUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print()
    print("===== FINAL =====")
    print("TRAJECTORIES=" + str(len(trajectories)))
    print("CANDIDATES=" + str(len(score_records)))
    print("BFCL=" + str(benchmark_counts["BFCL"]))
    print(
        "MATH_SHEPHERD="
        + str(benchmark_counts["Math-Shepherd"])
    )
    print(
        "TOOLALPACA="
        + str(benchmark_counts["ToolAlpaca"])
    )
    print("ALL_EDGES_FORWARD=YES")
    print("DAG_VIOLATIONS=0")
    print("TEXT_WINDOW=3")
    print("SPARSE_EXPLICIT_LINK_THRESHOLD=2")
    print("STRUCTURED_SPARSE_NONZERO=0")
    print(
        "TERMINAL_SINK_EDGES="
        + str(terminal_sink_count)
    )
    print("ALPHA=" + repr(alpha))
    print(
        "H_HAT_FINITE_RATE="
        + str(audit["H_hat_finite_rate"])
    )
    print(
        "H_HAT_MIN="
        + str(audit["H_hat_min"])
    )
    print(
        "H_HAT_MAX="
        + str(audit["H_hat_max"])
    )
    print("POSTHOC_ACCESS=NO")
    print("TERRA_CALLS=0")
    print("STATUS=PASS")
    print(
        "NEXT=SIGNAL_AVAILABILITY_GATES_AND_DECOUPLE_PRE_SCORE"
    )


if __name__ == "__main__":
    main()
