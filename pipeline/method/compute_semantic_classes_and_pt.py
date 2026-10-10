#!/usr/bin/env python3

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)


ROOT = Path("__DECOUPLE_ROOT__")

K8_ROOT = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1D_SEMANTIC/K8_CONTINUATIONS"
)

OUT_ROOT = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1D_SEMANTIC/SEMANTIC_CLASSES_PT"
)

CONFIG_PATH = (
    ROOT
    / "15_DEV_FREEZE/config/"
      "semantic_equivalence.json"
)

THRESHOLD_RESULT_PATH = (
    ROOT
    / "15_DEV_FREEZE/results/"
      "semantic_entailment_threshold.json"
)

CLASSIFIER_CONTRACT_PATH = (
    ROOT
    / "03_TECHNICAL_DOCS/01_STEP1/"
      "SEMANTIC_CLASSIFIER_FREEZE/"
      "classifier_contract.json"
)

MODEL_ID = "microsoft/deberta-v2-xlarge-mnli"
MODEL_REVISION = (
    "2b65bccdedcead4bc685988bcc30153d4922a789"
)

EXPECTED_K = 8
EXPECTED_CANDIDATES = 631
EXPECTED_CONTINUATIONS = 5048
EXPECTED_THRESHOLD = 0.239

NLI_BATCH_SIZE = 16
MAX_NLI_LENGTH = 512

OUT_CONTINUATIONS = (
    OUT_ROOT
    / "semantic_continuations.jsonl"
)

OUT_CANDIDATES = (
    OUT_ROOT
    / "semantic_candidate_scores.jsonl"
)

OUT_CLASSES = (
    OUT_ROOT
    / "semantic_class_index.jsonl"
)

OUT_AUDIT = (
    OUT_ROOT
    / "semantic_audit.json"
)

OUT_COMPUTE = (
    OUT_ROOT
    / "compute_ledger.json"
)

OUT_MANIFEST = (
    OUT_ROOT
    / "semantic_manifest.json"
)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(path.read_bytes())


def sha256_text(text):
    return sha256_bytes(
        text.encode("utf-8")
    )


def canonical_json(obj):
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def normalize_text(text):
    text = unicodedata.normalize(
        "NFKC",
        str(text),
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


def normalize_math_fragment(text):
    text = normalize_text(text)

    replacements = {
        "−": "-",
        "–": "-",
        "—": "-",
        "\\,": "",
        "\\;": "",
        "\\!": "",
        "\\left": "",
        "\\right": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(
        r"\s*([=+\-*/^<>])\s*",
        r"\1",
        text,
    )

    return text.strip(
        " .,:;"
    )


def extract_math_assertion(text):
    """
    Deterministic Pilot operationalization of the
    Master Specification instruction to canonicalize
    mathematical continuations by the next asserted
    proposition/equation.

    Priority:
      1. first display/inline LaTeX fragment containing
         a relational operator;
      2. first sentence containing a relational operator;
      3. first nonempty sentence/proposition.
    """

    text = normalize_text(text)

    latex_patterns = [
        r"\\\[(.+?)\\\]",
        r"\\\((.+?)\\\)",
        r"\$\$(.+?)\$\$",
        r"\$(.+?)\$",
    ]

    fragments = []

    for pattern in latex_patterns:
        fragments.extend(
            re.findall(
                pattern,
                text,
                flags=re.DOTALL,
            )
        )

    relation_pattern = re.compile(
        r"(=|<=|>=|<|>|\\le|\\ge|\\approx|\\neq)"
    )

    for fragment in fragments:
        if relation_pattern.search(fragment):
            return (
                "MATH_ASSERTION:"
                + normalize_math_fragment(
                    fragment
                )
            )

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    for sentence in sentences:
        if relation_pattern.search(sentence):
            return (
                "MATH_ASSERTION:"
                + normalize_math_fragment(
                    sentence
                )
            )

    for sentence in sentences:
        sentence = sentence.strip()

        if sentence:
            return (
                "MATH_PROPOSITION:"
                + normalize_math_fragment(
                    sentence
                )
            )

    return "MATH_EMPTY"


def normalize_value(value):
    if isinstance(value, dict):
        return {
            str(k): normalize_value(value[k])
            for k in sorted(value)
        }

    if isinstance(value, list):
        return [
            normalize_value(x)
            for x in value
        ]

    if isinstance(value, tuple):
        return [
            normalize_value(x)
            for x in value
        ]

    if isinstance(value, str):
        return normalize_text(value)

    if isinstance(
        value,
        (
            int,
            float,
            bool,
        ),
    ) or value is None:
        return value

    return normalize_text(str(value))


def canonical_tool_action(row):
    calls = (
        row.get("continuation", {})
        .get("function_calls", [])
    )

    if not calls:
        calls = row.get(
            "function_calls",
            [],
        )

    normalized_calls = []

    for call in calls:
        name = normalize_text(
            call.get("name", "")
        )

        arguments = normalize_value(
            call.get(
                "arguments",
                {},
            )
        )

        normalized_calls.append(
            {
                "name": name,
                "arguments": arguments,
            }
        )

    # Multiple calls emitted in the same model response
    # constitute one joint action. Sorting removes
    # serialization-order variation while preserving
    # multiplicity.
    normalized_calls = sorted(
        normalized_calls,
        key=canonical_json,
    )

    return (
        "TOOL_ACTION:"
        + canonical_json(
            normalized_calls
        )
    )


def read_candidate_file(path):
    rows = []

    with path.open(
        encoding="utf-8"
    ) as f:
        for line in f:
            if not line.strip():
                continue

            row = json.loads(line)

            rows.append(row)

    rows.sort(
        key=lambda x:
            int(
                x["continuation_index"]
            )
    )

    return rows


def tree_digest(paths):
    h = hashlib.sha256()

    for path in sorted(paths):
        rel = str(
            path.relative_to(ROOT)
        )

        h.update(
            rel.encode("utf-8")
        )

        h.update(b"\0")

        with path.open("rb") as f:
            while True:
                block = f.read(
                    1024 * 1024
                )

                if not block:
                    break

                h.update(block)

        h.update(b"\0")

    return h.hexdigest()


def load_frozen_contract():
    config = json.loads(
        CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )

    threshold_result = json.loads(
        THRESHOLD_RESULT_PATH.read_text(
            encoding="utf-8"
        )
    )

    threshold = float(
        config[
            "directional_threshold"
        ]
    )

    if abs(
        threshold
        - EXPECTED_THRESHOLD
    ) > 1e-12:
        raise RuntimeError(
            "Frozen threshold mismatch: "
            + str(threshold)
        )

    if abs(
        float(
            threshold_result[
                "threshold"
            ]
        )
        - threshold
    ) > 1e-12:
        raise RuntimeError(
            "Threshold artifact mismatch."
        )

    classifier = config[
        "classifier"
    ]

    if (
        classifier["model_id"]
        != MODEL_ID
    ):
        raise RuntimeError(
            "Frozen model ID mismatch."
        )

    if (
        classifier["revision"]
        != MODEL_REVISION
    ):
        raise RuntimeError(
            "Frozen revision mismatch."
        )

    return (
        config,
        threshold_result,
        threshold,
    )


def prepare_candidate(rows):
    if len(rows) != EXPECTED_K:
        raise RuntimeError(
            "Expected K=8 rows, got "
            + str(len(rows))
        )

    expected_indices = list(
        range(
            1,
            EXPECTED_K + 1,
        )
    )

    actual_indices = [
        int(
            row[
                "continuation_index"
            ]
        )
        for row in rows
    ]

    if actual_indices != expected_indices:
        raise RuntimeError(
            "Continuation indices mismatch: "
            + repr(actual_indices)
        )

    first = rows[0]

    benchmark = first["benchmark"]
    instance_id = first["instance_id"]
    step_index = int(
        first["step_index"]
    )
    prefix_hash = first[
        "prefix_hash"
    ]

    prepared = []

    for row in rows:
        if (
            row["benchmark"]
            != benchmark
        ):
            raise RuntimeError(
                "Benchmark mismatch."
            )

        if (
            row["instance_id"]
            != instance_id
        ):
            raise RuntimeError(
                "Instance mismatch."
            )

        if (
            int(row["step_index"])
            != step_index
        ):
            raise RuntimeError(
                "Step mismatch."
            )

        if (
            row["prefix_hash"]
            != prefix_hash
        ):
            raise RuntimeError(
                "Prefix hash mismatch."
            )

        if bool(
            row.get(
                "posthoc_fields_used",
                False,
            )
        ):
            raise RuntimeError(
                "posthoc_fields_used=True"
            )

        ctype = row[
            "continuation_type"
        ]

        item = {
            "benchmark":
                benchmark,
            "instance_id":
                instance_id,
            "step_index":
                step_index,
            "prefix_hash":
                prefix_hash,
            "continuation_index":
                int(
                    row[
                        "continuation_index"
                    ]
                ),
            "continuation_type":
                ctype,
            "canonicalization_method":
                None,
            "canonical_key":
                None,
            "canonical_key_sha256":
                None,
            "residual_text":
                None,
            "residual_text_sha256":
                None,
        }

        if ctype in (
            "tool_call",
            "joint_tool_call",
        ):
            key = canonical_tool_action(
                row
            )

            item[
                "canonicalization_method"
            ] = (
                "tool_function_identity_"
                "plus_normalized_arguments"
            )

            item[
                "canonical_key"
            ] = key

            item[
                "canonical_key_sha256"
            ] = sha256_text(key)

        elif (
            ctype
            == "no_observable_output"
        ):
            key = (
                "NO_OBSERVABLE_OUTPUT"
            )

            item[
                "canonicalization_method"
            ] = (
                "fixed_no_observable_class"
            )

            item[
                "canonical_key"
            ] = key

            item[
                "canonical_key_sha256"
            ] = sha256_text(key)

        elif (
            ctype
            == "assistant_text"
        ):
            text = (
                row.get(
                    "continuation",
                    {},
                )
                .get(
                    "text",
                    row.get(
                        "visible_text",
                        "",
                    ),
                )
            )

            text = normalize_text(text)

            if benchmark == "Math-Shepherd":
                key = (
                    extract_math_assertion(
                        text
                    )
                )

                item[
                    "canonicalization_method"
                ] = (
                    "math_next_asserted_"
                    "proposition_or_equation"
                )

                item[
                    "canonical_key"
                ] = key

                item[
                    "canonical_key_sha256"
                ] = sha256_text(key)

            else:
                item[
                    "canonicalization_method"
                ] = (
                    "residual_text_"
                    "bidirectional_entailment"
                )

                item[
                    "residual_text"
                ] = text

                item[
                    "residual_text_sha256"
                ] = sha256_text(text)

        else:
            raise RuntimeError(
                "Unexpected continuation_type="
                + repr(ctype)
            )

        prepared.append(item)

    return prepared


def collect_nli_pairs(candidates):
    pair_records = []

    for candidate_key, items in candidates.items():
        residual = [
            item
            for item in items
            if (
                item[
                    "canonicalization_method"
                ]
                == (
                    "residual_text_"
                    "bidirectional_entailment"
                )
            )
        ]

        residual.sort(
            key=lambda x:
                x["continuation_index"]
        )

        for i in range(len(residual)):
            for j in range(
                i + 1,
                len(residual),
            ):
                a = residual[i]
                b = residual[j]

                pair_records.append(
                    {
                        "candidate_key":
                            candidate_key,
                        "i":
                            a[
                                "continuation_index"
                            ],
                        "j":
                            b[
                                "continuation_index"
                            ],
                        "text_i":
                            a[
                                "residual_text"
                            ],
                        "text_j":
                            b[
                                "residual_text"
                            ],
                    }
                )

    return pair_records


def score_directional_entailment(
    tokenizer,
    model,
    pairs,
    device,
):
    scores = []

    model.eval()

    id2label = {
        int(k): str(v).upper()
        for k, v
        in model.config.id2label.items()
    }

    entailment_ids = [
        idx
        for idx, label
        in id2label.items()
        if label == "ENTAILMENT"
    ]

    if len(entailment_ids) != 1:
        raise RuntimeError(
            "Cannot uniquely identify "
            "ENTAILMENT label."
        )

    entailment_id = (
        entailment_ids[0]
    )

    forward_calls = 0

    with torch.inference_mode():
        for start in range(
            0,
            len(pairs),
            NLI_BATCH_SIZE,
        ):
            batch = pairs[
                start:
                start
                + NLI_BATCH_SIZE
            ]

            premises = [
                x[0]
                for x in batch
            ]

            hypotheses = [
                x[1]
                for x in batch
            ]

            encoded = tokenizer(
                premises,
                hypotheses,
                padding=True,
                truncation=True,
                max_length=
                    MAX_NLI_LENGTH,
                return_tensors="pt",
            )

            encoded = {
                k: v.to(device)
                for k, v
                in encoded.items()
            }

            logits = model(
                **encoded
            ).logits

            probabilities = (
                torch.softmax(
                    logits,
                    dim=-1,
                )[
                    :,
                    entailment_id,
                ]
            )

            scores.extend(
                float(x)
                for x
                in probabilities.cpu()
            )

            forward_calls += 1

    return (
        scores,
        forward_calls,
        entailment_id,
    )


def run_bidirectional_nli(
    pair_records,
    threshold,
):
    if not pair_records:
        return {}, {
            "undirected_pairs": 0,
            "directional_pairs": 0,
            "model_forward_calls": 0,
        }

    print(
        "RESIDUAL_UNDIRECTED_PAIRS="
        + str(len(pair_records)),
        flush=True,
    )

    directional = []

    for record in pair_records:
        directional.append(
            (
                record["text_i"],
                record["text_j"],
            )
        )

        directional.append(
            (
                record["text_j"],
                record["text_i"],
            )
        )

    print(
        "RESIDUAL_DIRECTIONAL_PAIRS="
        + str(len(directional)),
        flush=True,
    )

    print(
        "NLI_DEVICE=cpu",
        flush=True,
    )

    tokenizer = (
        AutoTokenizer
        .from_pretrained(
            MODEL_ID,
            revision=
                MODEL_REVISION,
            use_fast=False,
        )
    )

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(
            MODEL_ID,
            revision=
                MODEL_REVISION,
        )
    )

    device = torch.device(
        "cpu"
    )

    model.to(device)

    (
        scores,
        forward_calls,
        entailment_id,
    ) = score_directional_entailment(
        tokenizer,
        model,
        directional,
        device,
    )

    equivalence = {}

    for idx, record in enumerate(
        pair_records
    ):
        p_ij = scores[
            2 * idx
        ]

        p_ji = scores[
            2 * idx + 1
        ]

        eq = (
            p_ij >= threshold
            and p_ji >= threshold
        )

        key = (
            record["candidate_key"],
            record["i"],
            record["j"],
        )

        equivalence[key] = {
            "p_i_to_j":
                p_ij,
            "p_j_to_i":
                p_ji,
            "equivalent":
                bool(eq),
        }

    compute = {
        "undirected_pairs":
            len(pair_records),
        "directional_pairs":
            len(directional),
        "model_forward_calls":
            forward_calls,
        "entailment_label_id":
            entailment_id,
        "device":
            "cpu",
    }

    return equivalence, compute


def pair_equivalent(
    candidate_key,
    i,
    j,
    equivalence,
):
    if i == j:
        return True

    a = min(i, j)
    b = max(i, j)

    record = equivalence.get(
        (
            candidate_key,
            a,
            b,
        )
    )

    if record is None:
        raise RuntimeError(
            "Missing residual pair "
            f"{candidate_key} "
            f"{a},{b}"
        )

    return bool(
        record["equivalent"]
    )


def build_candidate_classes(
    candidate_key,
    items,
    equivalence,
):
    """
    Deterministic class construction.

    Exact deterministic canonical keys are grouped
    exactly.

    Residual-text items use a deterministic complete-link
    rule in continuation_index order. A continuation joins
    the first existing residual class only when it is
    bidirectionally equivalent to every member already in
    that class. Otherwise it starts a new class.

    This prevents non-transitive pairwise NLI chains from
    silently merging mutually non-equivalent endpoints.
    """

    exact_groups = defaultdict(
        list
    )

    residual = []

    for item in sorted(
        items,
        key=lambda x:
            x["continuation_index"],
    ):
        if (
            item["residual_text"]
            is not None
        ):
            residual.append(item)
        else:
            group_key = (
                item[
                    "canonicalization_method"
                ],
                item[
                    "canonical_key"
                ],
            )

            exact_groups[
                group_key
            ].append(item)

    classes = []

    for _, members in sorted(
        exact_groups.items(),
        key=lambda kv:
            min(
                x[
                    "continuation_index"
                ]
                for x in kv[1]
            ),
    ):
        classes.append(
            list(members)
        )

    residual_classes = []

    for item in sorted(
        residual,
        key=lambda x:
            x["continuation_index"],
    ):
        placed = False

        for semantic_class in (
            residual_classes
        ):
            if all(
                pair_equivalent(
                    candidate_key,
                    item[
                        "continuation_index"
                    ],
                    member[
                        "continuation_index"
                    ],
                    equivalence,
                )
                for member
                in semantic_class
            ):
                semantic_class.append(
                    item
                )
                placed = True
                break

        if not placed:
            residual_classes.append(
                [item]
            )

    classes.extend(
        residual_classes
    )

    classes.sort(
        key=lambda cls:
            min(
                x["continuation_index"]
                for x in cls
            )
    )

    return classes


def main():
    print(
        "===== STEP1D SEMANTIC "
        "CANONICALIZATION CLUSTERING "
        "AND P_T ====="
    )

    (
        frozen_config,
        threshold_result,
        threshold,
    ) = load_frozen_contract()

    print(
        "THRESHOLD="
        + str(threshold)
    )

    print(
        "MODEL="
        + MODEL_ID
    )

    print(
        "REVISION="
        + MODEL_REVISION
    )

    print(
        "TERRA_CALLS=0"
    )

    print(
        "POSTHOC_ACCESS=NO"
    )

    candidate_files = sorted(
        K8_ROOT.rglob(
            "*__k8.jsonl"
        )
    )

    print(
        "CANDIDATE_FILES="
        + str(
            len(candidate_files)
        )
    )

    if (
        len(candidate_files)
        != EXPECTED_CANDIDATES
    ):
        raise RuntimeError(
            "Candidate file count mismatch."
        )

    candidates = {}

    type_counts = Counter()
    benchmark_counts = Counter()
    total_rows = 0

    for path in candidate_files:
        rows = read_candidate_file(
            path
        )

        prepared = prepare_candidate(
            rows
        )

        first = prepared[0]

        candidate_key = (
            first["benchmark"],
            first["instance_id"],
            first["step_index"],
        )

        if candidate_key in candidates:
            raise RuntimeError(
                "Duplicate candidate key: "
                + repr(candidate_key)
            )

        candidates[
            candidate_key
        ] = prepared

        benchmark_counts[
            first["benchmark"]
        ] += 1

        for item in prepared:
            type_counts[
                item[
                    "continuation_type"
                ]
            ] += 1

            total_rows += 1

    if (
        total_rows
        != EXPECTED_CONTINUATIONS
    ):
        raise RuntimeError(
            "Continuation count mismatch."
        )

    print(
        "CONTINUATIONS="
        + str(total_rows)
    )

    for key in sorted(
        type_counts
    ):
        print(
            "TYPE_"
            + key
            + "="
            + str(type_counts[key])
        )

    pair_records = (
        collect_nli_pairs(
            candidates
        )
    )

    (
        equivalence,
        nli_compute,
    ) = run_bidirectional_nli(
        pair_records,
        threshold,
    )

    continuation_outputs = []
    candidate_outputs = []
    class_outputs = []

    class_count_histogram = Counter()

    p_values = []
    entropy_values = []

    for candidate_key in sorted(
        candidates
    ):
        items = candidates[
            candidate_key
        ]

        classes = (
            build_candidate_classes(
                candidate_key,
                items,
                equivalence,
            )
        )

        class_count = len(
            classes
        )

        class_count_histogram[
            class_count
        ] += 1

        masses = [
            len(cls)
            / EXPECTED_K
            for cls in classes
        ]

        h_sem = -sum(
            mass
            * math.log(mass)
            for mass in masses
            if mass > 0.0
        )

        p_t = (
            h_sem
            / math.log(
                EXPECTED_K
            )
        )

        if not math.isfinite(
            p_t
        ):
            raise RuntimeError(
                "Non-finite p_t."
            )

        if (
            p_t < -1e-12
            or p_t > 1.0 + 1e-12
        ):
            raise RuntimeError(
                "p_t outside [0,1]: "
                + str(p_t)
            )

        p_t = min(
            1.0,
            max(
                0.0,
                p_t,
            ),
        )

        p_values.append(
            p_t
        )

        entropy_values.append(
            h_sem
        )

        benchmark = (
            candidate_key[0]
        )

        instance_id = (
            candidate_key[1]
        )

        step_index = (
            candidate_key[2]
        )

        class_descriptions = []

        for class_idx, cls in enumerate(
            classes,
            start=1,
        ):
            class_id = (
                f"C{class_idx:02d}"
            )

            indices = sorted(
                item[
                    "continuation_index"
                ]
                for item in cls
            )

            class_mass = (
                len(cls)
                / EXPECTED_K
            )

            class_methods = sorted(
                set(
                    item[
                        "canonicalization_method"
                    ]
                    for item in cls
                )
            )

            class_record = {
                "benchmark":
                    benchmark,
                "instance_id":
                    instance_id,
                "step_index":
                    step_index,
                "class_id":
                    class_id,
                "count":
                    len(cls),
                "mass":
                    class_mass,
                "continuation_indices":
                    indices,
                "canonicalization_methods":
                    class_methods,
            }

            class_outputs.append(
                class_record
            )

            class_descriptions.append(
                {
                    "class_id":
                        class_id,
                    "count":
                        len(cls),
                    "mass":
                        class_mass,
                    "continuation_indices":
                        indices,
                }
            )

            for item in cls:
                output = dict(
                    item
                )

                output[
                    "semantic_class_id"
                ] = class_id

                output[
                    "semantic_class_count"
                ] = len(cls)

                output[
                    "semantic_class_mass"
                ] = class_mass

                # Avoid duplicating full residual text in
                # the derived archive. The hash preserves
                # traceability to the frozen K8 source.
                output.pop(
                    "residual_text",
                    None,
                )

                continuation_outputs.append(
                    output
                )

        candidate_outputs.append(
            {
                "benchmark":
                    benchmark,
                "instance_id":
                    instance_id,
                "step_index":
                    step_index,
                "prefix_hash":
                    items[0][
                        "prefix_hash"
                    ],
                "K":
                    EXPECTED_K,
                "semantic_class_count":
                    class_count,
                "classes":
                    class_descriptions,
                "H_sem":
                    h_sem,
                "p_t":
                    p_t,
            }
        )

    continuation_outputs.sort(
        key=lambda x: (
            x["benchmark"],
            x["instance_id"],
            x["step_index"],
            x["continuation_index"],
        )
    )

    candidate_outputs.sort(
        key=lambda x: (
            x["benchmark"],
            x["instance_id"],
            x["step_index"],
        )
    )

    class_outputs.sort(
        key=lambda x: (
            x["benchmark"],
            x["instance_id"],
            x["step_index"],
            x["class_id"],
        )
    )

    OUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    def write_jsonl(
        path,
        records,
    ):
        with path.open(
            "w",
            encoding="utf-8",
        ) as f:
            for record in records:
                f.write(
                    json.dumps(
                        record,
                        sort_keys=True,
                        ensure_ascii=False,
                    )
                )
                f.write("\n")

    write_jsonl(
        OUT_CONTINUATIONS,
        continuation_outputs,
    )

    write_jsonl(
        OUT_CANDIDATES,
        candidate_outputs,
    )

    write_jsonl(
        OUT_CLASSES,
        class_outputs,
    )

    finite_count = sum(
        math.isfinite(x)
        for x in p_values
    )

    audit = {
        "status": "PASS",
        "candidate_count":
            len(candidate_outputs),
        "continuation_count":
            len(
                continuation_outputs
            ),
        "K":
            EXPECTED_K,
        "threshold":
            threshold,
        "model_id":
            MODEL_ID,
        "model_revision":
            MODEL_REVISION,
        "benchmark_candidate_counts":
            dict(
                sorted(
                    benchmark_counts.items()
                )
            ),
        "continuation_type_counts":
            dict(
                sorted(
                    type_counts.items()
                )
            ),
        "semantic_class_count_histogram":
            {
                str(k): v
                for k, v
                in sorted(
                    class_count_histogram.items()
                )
            },
        "p_t_finite_count":
            finite_count,
        "p_t_finite_rate":
            finite_count
            / len(p_values),
        "p_t_min":
            min(p_values),
        "p_t_max":
            max(p_values),
        "p_t_mean":
            sum(p_values)
            / len(p_values),
        "H_sem_min":
            min(entropy_values),
        "H_sem_max":
            max(entropy_values),
        "residual_nli":
            nli_compute,
        "terra_calls":
            0,
        "posthoc_access":
            False,
        "k8_regenerated":
            False,
        "threshold_retuned":
            False,
    }

    OUT_AUDIT.write_text(
        json.dumps(
            audit,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    compute = {
        "status": "PASS",
        "terra_model_calls":
            0,
        "external_api_calls":
            0,
        "local_nli_model":
            MODEL_ID,
        "local_nli_revision":
            MODEL_REVISION,
        "local_nli_undirected_pairs":
            nli_compute[
                "undirected_pairs"
            ],
        "local_nli_directional_pairs":
            nli_compute[
                "directional_pairs"
            ],
        "local_nli_forward_calls":
            nli_compute[
                "model_forward_calls"
            ],
        "local_nli_device":
            nli_compute[
                "device"
            ],
    }

    OUT_COMPUTE.write_text(
        json.dumps(
            compute,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    input_tree_sha256 = (
        tree_digest(
            candidate_files
        )
    )

    script_path = Path(
        __file__
    ).resolve()

    manifest = {
        "status": "FROZEN",
        "stage":
            "STEP1D_SEMANTIC_CLASSES_PT",
        "input": {
            "root":
                str(
                    K8_ROOT.relative_to(
                        ROOT
                    )
                ),
            "candidate_files":
                len(
                    candidate_files
                ),
            "continuations":
                total_rows,
            "K":
                EXPECTED_K,
            "tree_sha256":
                input_tree_sha256,
        },
        "frozen_semantic_classifier": {
            "model_id":
                MODEL_ID,
            "revision":
                MODEL_REVISION,
            "threshold":
                threshold,
            "equivalence_rule":
                frozen_config[
                    "equivalence_rule"
                ],
            "threshold_result_sha256":
                sha256_file(
                    THRESHOLD_RESULT_PATH
                ),
            "semantic_config_sha256":
                sha256_file(
                    CONFIG_PATH
                ),
            "classifier_contract_sha256":
                sha256_file(
                    CLASSIFIER_CONTRACT_PATH
                ),
        },
        "class_construction": {
            "tool_calls":
                "exact normalized function identity and arguments",
            "joint_tool_calls":
                "sorted atomic joint tool action",
            "math":
                "next asserted proposition or equation",
            "residual_text":
                "bidirectional entailment with deterministic complete-link classes",
            "residual_class_order":
                "ascending continuation_index",
            "no_observable_output":
                "fixed explicit semantic class",
        },
        "outputs": {
            "semantic_continuations_sha256":
                sha256_file(
                    OUT_CONTINUATIONS
                ),
            "semantic_candidate_scores_sha256":
                sha256_file(
                    OUT_CANDIDATES
                ),
            "semantic_class_index_sha256":
                sha256_file(
                    OUT_CLASSES
                ),
            "semantic_audit_sha256":
                sha256_file(
                    OUT_AUDIT
                ),
            "compute_ledger_sha256":
                sha256_file(
                    OUT_COMPUTE
                ),
        },
        "implementation_sha256":
            sha256_file(
                script_path
            ),
        "posthoc_access":
            False,
        "terra_calls":
            0,
        "k8_regenerated":
            False,
        "threshold_retuned":
            False,
        "next":
            "HYBRID_GRAPH_AND_H_HAT",
    }

    OUT_MANIFEST.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    if (
        len(candidate_outputs)
        != EXPECTED_CANDIDATES
    ):
        raise RuntimeError(
            "Final candidate count mismatch."
        )

    if (
        len(continuation_outputs)
        != EXPECTED_CONTINUATIONS
    ):
        raise RuntimeError(
            "Final continuation count mismatch."
        )

    if finite_count != EXPECTED_CANDIDATES:
        raise RuntimeError(
            "Non-finite p_t detected."
        )

    print()
    print("===== FINAL =====")
    print(
        "CANDIDATES="
        + str(
            len(candidate_outputs)
        )
    )
    print(
        "CONTINUATIONS="
        + str(
            len(continuation_outputs)
        )
    )
    print("K=8")
    print(
        "THRESHOLD="
        + str(threshold)
    )
    print(
        "RESIDUAL_NLI_UNDIRECTED_PAIRS="
        + str(
            nli_compute[
                "undirected_pairs"
            ]
        )
    )
    print(
        "RESIDUAL_NLI_DIRECTIONAL_PAIRS="
        + str(
            nli_compute[
                "directional_pairs"
            ]
        )
    )
    print(
        "P_T_FINITE_RATE="
        + str(
            audit[
                "p_t_finite_rate"
            ]
        )
    )
    print(
        "P_T_MIN="
        + str(
            audit[
                "p_t_min"
            ]
        )
    )
    print(
        "P_T_MAX="
        + str(
            audit[
                "p_t_max"
            ]
        )
    )
    print("POSTHOC_ACCESS=NO")
    print("TERRA_CALLS=0")
    print("K8_REGENERATED=NO")
    print("THRESHOLD_RETUNED=NO")
    print("STATUS=PASS")
    print(
        "NEXT=HYBRID_GRAPH_AND_H_HAT"
    )


if __name__ == "__main__":
    main()
