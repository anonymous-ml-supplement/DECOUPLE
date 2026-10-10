#!/usr/bin/env python3

import json


SUPPORTED_BENCHMARKS = {
    "BFCL",
    "Math-Shepherd",
    "ToolAlpaca",
}

SUPPORTED_OPERATORS = {
    "V_refine",
    "V_oracle",
}


def descriptor_key(
    benchmark,
    instance_id,
    step_index,
):
    return (
        benchmark,
        instance_id,
        int(step_index),
    )


def build_descriptor_index(rows):
    index = {}

    for row in rows:
        key = descriptor_key(
            row["benchmark"],
            row["instance_id"],
            row["step_index"],
        )

        if key in index:
            raise RuntimeError(
                "DUPLICATE_DESCRIPTOR="
                + repr(key)
            )

        index[key] = row

    return index


def build_oracle_index(rows):
    index = {}

    for row in rows:
        key = descriptor_key(
            row["benchmark"],
            row["instance_id"],
            row["step_index"],
        )

        if key in index:
            raise RuntimeError(
                "DUPLICATE_ORACLE_ROW="
                + repr(key)
            )

        index[key] = row

    return index


def validate_common_branch(branch):
    benchmark = branch["benchmark"]
    operator = branch["intervention_operator"]

    if benchmark not in SUPPORTED_BENCHMARKS:
        raise RuntimeError(
            "UNSUPPORTED_BENCHMARK="
            + benchmark
        )

    if operator not in SUPPORTED_OPERATORS:
        raise RuntimeError(
            "UNSUPPORTED_OPERATOR="
            + operator
        )

    steps = [
        int(x)
        for x in branch[
            "selected_steps_chronological"
        ]
    ]

    if not steps:
        raise RuntimeError(
            "EMPTY_SELECTED_STEPS"
        )

    if steps != sorted(steps):
        raise RuntimeError(
            "STEPS_NOT_CHRONOLOGICAL"
        )

    if len(steps) != len(set(steps)):
        raise RuntimeError(
            "DUPLICATE_SELECTED_STEPS"
        )

    if int(
        branch["first_modified_step"]
    ) != steps[0]:
        raise RuntimeError(
            "FIRST_MODIFIED_STEP_MISMATCH"
        )

    if (
        branch.get(
            "process_selected_steps_chronologically"
        )
        is not True
    ):
        raise RuntimeError(
            "CHRONOLOGICAL_PROCESSING_NOT_FROZEN"
        )

    return steps


def bind_refine_branch(
    branch,
    descriptor_index,
):
    steps = validate_common_branch(
        branch
    )

    if (
        branch["intervention_operator"]
        != "V_refine"
    ):
        raise RuntimeError(
            "NOT_V_REFINE_BRANCH"
        )

    bound = []

    for step in steps:
        key = descriptor_key(
            branch["benchmark"],
            branch["instance_id"],
            step,
        )

        if key not in descriptor_index:
            raise RuntimeError(
                "DESCRIPTOR_MISSING="
                + repr(key)
            )

        desc = descriptor_index[key]

        if (
            desc.get(
                "runtime_history_source"
            )
            !=
            "STEP3E_EXACT_CURRENT_PRE_STEP_BRANCH_STATE"
        ):
            raise RuntimeError(
                "RUNTIME_HISTORY_SOURCE_MISMATCH="
                + repr(key)
            )

        if (
            desc.get(
                "archived_history_may_replace_runtime_branch_history"
            )
            is not False
        ):
            raise RuntimeError(
                "ARCHIVED_HISTORY_REPLACEMENT_FORBIDDEN="
                + repr(key)
            )

        if (
            desc.get("operator")
            != "V_refine"
        ):
            raise RuntimeError(
                "DESCRIPTOR_OPERATOR_MISMATCH="
                + repr(key)
            )

        bound.append(
            {
                "step_index":
                    step,

                "candidate_kind":
                    desc[
                        "candidate_kind"
                    ],

                "archived_candidate_step":
                    desc[
                        "archived_candidate_step"
                    ],

                "source_archive_path":
                    desc[
                        "source_archive_path"
                    ],

                "source_archive_sha256":
                    desc[
                        "source_archive_sha256"
                    ],

                "runtime_history_rule":
                    "USE_CURRENT_MODIFIED_BRANCH_STATE",

                "descriptor":
                    desc,
            }
        )

    return {
        "execution_id":
            branch["execution_id"],

        "benchmark":
            branch["benchmark"],

        "operator":
            "V_refine",

        "selected_steps":
            steps,

        "bound_steps":
            bound,

        "joint_terminal_replay_required":
            len(steps) > 1,

        "singleton_gain_summation_allowed":
            False,
    }


def bind_oracle_branch(
    branch,
    oracle_index,
):
    steps = validate_common_branch(
        branch
    )

    if (
        branch["intervention_operator"]
        != "V_oracle"
    ):
        raise RuntimeError(
            "NOT_V_ORACLE_BRANCH"
        )

    if (
        branch["benchmark"]
        == "Math-Shepherd"
    ):
        raise RuntimeError(
            "MATH_ORACLE_FORBIDDEN"
        )

    bound = []

    for step in steps:
        key = descriptor_key(
            branch["benchmark"],
            branch["instance_id"],
            step,
        )

        if key not in oracle_index:
            raise RuntimeError(
                "ORACLE_ROW_MISSING="
                + repr(key)
            )

        row = oracle_index[key]

        if (
            row.get("patch_defined")
            is not True
        ):
            raise RuntimeError(
                "ORACLE_PATCH_NOT_DEFINED="
                + repr(key)
            )

        if (
            row.get("diagnostic_only")
            is not True
        ):
            raise RuntimeError(
                "ORACLE_NOT_DIAGNOSTIC="
                + repr(key)
            )

        operation = row[
            "patch_operation"
        ]

        if (
            operation.get("operation")
            != "REPLACE_SELECTED_TOOL_ACTION"
        ):
            raise RuntimeError(
                "UNSUPPORTED_ORACLE_OPERATION="
                + repr(key)
            )

        bound.append(
            {
                "step_index":
                    step,

                "candidate_kind":
                    row[
                        "candidate_kind"
                    ],

                "replacement_payload":
                    operation[
                        "replacement_payload"
                    ],

                "replacement_semantics":
                    operation[
                        "replacement_semantics"
                    ],

                "oracle_target":
                    row[
                        "oracle_target"
                    ],

                "runtime_operation":
                    "REPLACE_SELECTED_TOOL_ACTION",

                "oracle_row":
                    row,
            }
        )

    return {
        "execution_id":
            branch["execution_id"],

        "benchmark":
            branch["benchmark"],

        "operator":
            "V_oracle",

        "selected_steps":
            steps,

        "bound_steps":
            bound,

        "diagnostic_only":
            True,

        "joint_terminal_replay_required":
            True,
    }


def bind_execution_branch(
    branch,
    descriptor_index,
    oracle_index,
):
    operator = branch[
        "intervention_operator"
    ]

    if operator == "V_refine":
        return bind_refine_branch(
            branch,
            descriptor_index,
        )

    if operator == "V_oracle":
        return bind_oracle_branch(
            branch,
            oracle_index,
        )

    raise RuntimeError(
        "UNKNOWN_OPERATOR="
        + str(operator)
    )


def math_runtime_history(
    problem_text,
    generated_steps,
):
    history = [
        {
            "type":
                "problem",

            "content":
                problem_text,
        }
    ]

    for index, text in enumerate(
        generated_steps,
        start=1,
    ):
        history.append(
            {
                "type":
                    "math_reasoning_step",

                "step_index":
                    index,

                "content":
                    text,

                "observation":
                    "",
            }
        )

    return history


def render_math_causal_history(
    history,
):
    rendered = []

    for item in history:
        item_type = item.get(
            "type"
        )

        if item_type == "problem":
            rendered.append(
                "USER_OR_PROBLEM:\n"
                + item[
                    "content"
                ]
            )

        elif (
            item_type
            == "math_reasoning_step"
        ):
            rendered.append(
                "PRIOR_REASONING_STEP:\n"
                + item[
                    "content"
                ]
            )

        else:
            raise RuntimeError(
                "UNKNOWN_MATH_HISTORY_TYPE="
                + str(item_type)
            )

    return "\n\n".join(
        rendered
    )


def math_local_continuation_prompt(
    history,
):
    rendered = (
        render_math_causal_history(
            history
        )
    )

    instruction = (
        "Generate exactly one possible next local "
        "reasoning step from the causal history. "
        "Do not solve or continue beyond that one step."
    )

    return (
        "You are sampling one local continuation "
        "from a frozen decision-time causal history "
        "for a research experiment.\n\n"
        + instruction
        + "\n\n"
        + "The sampled local decision must contain "
        + "no more than 256 non-reasoning output tokens."
        + "\n\nCAUSAL_HISTORY_BEGIN\n"
        + rendered
        + "\nCAUSAL_HISTORY_END"
    )


def normalize_math_answer(text):
    value = str(
        text
        if text is not None
        else ""
    ).strip()

    boxed = None

    marker = "\\boxed{"

    position = value.rfind(
        marker
    )

    if position >= 0:
        start = (
            position
            + len(marker)
        )

        depth = 1
        cursor = start

        while (
            cursor < len(value)
            and depth > 0
        ):
            char = value[cursor]

            if char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

            cursor += 1

        if depth == 0:
            boxed = value[
                start:
                cursor - 1
            ]

    if boxed is not None:
        value = boxed

    lower = value.lower()
    answer_marker = "answer is"

    position = lower.rfind(
        answer_marker
    )

    if position >= 0:
        value = value[
            position
            + len(answer_marker):
        ]

    value = value.strip()

    while (
        value
        and value[-1]
        in ".,;:!?"
    ):
        value = value[:-1].rstrip()

    if (
        len(value) >= 2
        and value[0] == "$"
        and value[-1] == "$"
    ):
        value = value[
            1:-1
        ].strip()

    value = value.replace(
        ",",
        "",
    )

    return value.strip()


def validate_bound_execution(
    bound,
):
    benchmark = bound[
        "benchmark"
    ]

    operator = bound[
        "operator"
    ]

    steps = bound[
        "selected_steps"
    ]

    if (
        benchmark
        == "Math-Shepherd"
        and operator
        != "V_refine"
    ):
        raise RuntimeError(
            "MATH_OPERATOR_INVALID"
        )

    if (
        operator == "V_refine"
        and len(
            bound[
                "bound_steps"
            ]
        )
        != len(steps)
    ):
        raise RuntimeError(
            "REFINE_BINDING_COUNT_MISMATCH"
        )

    if (
        operator == "V_oracle"
        and len(
            bound[
                "bound_steps"
            ]
        )
        != len(steps)
    ):
        raise RuntimeError(
            "ORACLE_BINDING_COUNT_MISMATCH"
        )

    return True
