#!/usr/bin/env python3


def runtime_history_json(items):
    result = []

    for item in items:
        if isinstance(item, dict):
            result.append(
                dict(item)
            )

        elif hasattr(
            item,
            "model_dump",
        ):
            result.append(
                item.model_dump(
                    exclude_none=True
                )
            )

        elif hasattr(
            item,
            "to_dict",
        ):
            result.append(
                item.to_dict()
            )

        else:
            result.append(
                {
                    "type":
                        type(item).__name__,
                    "repr":
                        repr(item),
                }
            )

    return result


def parse_bfcl_raw_function_call(text):
    import ast

    node = ast.parse(
        text,
        mode="eval",
    ).body

    if not isinstance(
        node,
        ast.Call,
    ):
        raise RuntimeError(
            "BFCL_ORACLE_CALL_NOT_AST_CALL="
            + text
        )

    if not isinstance(
        node.func,
        ast.Name,
    ):
        raise RuntimeError(
            "BFCL_ORACLE_CALL_NAME_INVALID="
            + text
        )

    if node.args:
        raise RuntimeError(
            "BFCL_ORACLE_POSITIONAL_ARGS_UNSUPPORTED="
            + text
        )

    arguments = {}

    for keyword in node.keywords:
        if keyword.arg is None:
            raise RuntimeError(
                "BFCL_ORACLE_KW_SPLAT_UNSUPPORTED="
                + text
            )

        arguments[
            keyword.arg
        ] = ast.literal_eval(
            keyword.value
        )

    return {
        "function_name":
            node.func.id,

        "arguments":
            arguments,
    }


def bfcl_apply_function_calls_v2(
    *,
    branch,
    state,
    trace_turn,
    step_index,
    function_calls,
    official_calls,
    source,
):
    worker = state[
        "worker"
    ]

    if (
        len(function_calls)
        != len(official_calls)
    ):
        raise RuntimeError(
            "BFCL_V2_CALL_COUNT_MISMATCH="
            + branch["execution_id"]
            + ":step="
            + str(step_index)
        )

    results = worker.execute(
        official_calls
    )

    if (
        len(results)
        != len(function_calls)
    ):
        raise RuntimeError(
            "BFCL_V2_EXECUTION_COUNT_MISMATCH="
            + branch["execution_id"]
            + ":step="
            + str(step_index)
        )

    outputs = []

    for call, result in zip(
        function_calls,
        results,
    ):
        out = {
            "type":
                "function_call_output",

            "call_id":
                call[
                    "call_id"
                ],

            "output":
                result,
        }

        state[
            "messages"
        ].append(
            out
        )

        outputs.append(
            out
        )

    trace_turn[
        "model_steps"
    ].append(
        {
            "step_index":
                step_index,

            "source":
                source,

            "function_calls":
                official_calls,

            "execution_results":
                results,

            "function_call_outputs":
                outputs,
        }
    )


def execute_bfcl_branch_v2(
    branch,
    branch_descriptors,
    bfcl_mod,
    descriptors,
    oracle_index,
    client,
):
    selected_steps = [
        int(x)
        for x in branch[
            "selected_steps_chronological"
        ]
    ]

    selected_set = set(
        selected_steps
    )

    desc_by_step = {
        int(desc["step_index"]):
            desc
        for desc in branch_descriptors
    }

    first_desc = desc_by_step[
        selected_steps[0]
    ]

    state = (
        bfcl_grounded_prefix_restore(
            branch,
            first_desc,
            bfcl_mod,
            descriptors,
        )
    )

    worker = state[
        "worker"
    ]

    compute_rows = []
    interventions = []

    try:
        contract = json.loads(
            REFINE_CONTRACT.read_text(
                encoding="utf-8"
            )
        )

        amendment = json.loads(
            REFINE_AMENDMENT.read_text(
                encoding="utf-8"
            )
        )

        critic_prompt = (
            contract[
                "critic"
            ][
                "prompt"
            ]
        )

        refiner_prompt = (
            amendment[
                "refiner"
            ][
                "prompt"
            ]
        )

        trace_turn = state[
            "trace_turns"
        ][-1]

        round_index = state[
            "current_round_index"
        ]

        next_step_index = (
            selected_steps[0]
        )

        round_terminated = False

        while True:
            if round_terminated:
                round_index += 1

                if (
                    round_index
                    >= len(
                        state[
                            "worker"
                        ].question
                    )
                ):
                    break

                user_turn = [
                    dict(x)
                    for x in state[
                        "worker"
                    ].question[
                        round_index
                    ]
                ]

                for message in user_turn:
                    if (
                        message.get(
                            "role"
                        )
                        == "system"
                    ):
                        message[
                            "role"
                        ] = "developer"

                state[
                    "messages"
                ].extend(
                    user_turn
                )

                trace_turn = {
                    "round_index":
                        round_index,

                    "user_messages":
                        user_turn,

                    "model_steps":
                        [],
                }

                state[
                    "trace_turns"
                ].append(
                    trace_turn
                )

                round_terminated = False

            is_selected = (
                next_step_index
                in selected_set
            )

            operator = branch[
                "intervention_operator"
            ]

            if is_selected:
                if operator == "V_refine":
                    desc = desc_by_step[
                        next_step_index
                    ]

                    current_history = (
                        runtime_history_json(
                            state[
                                "messages"
                            ]
                        )
                    )

                    critic_input = (
                        make_component_input(
                            critic_prompt,

                            current_history=
                                current_history,

                            archived_candidate_step=
                                desc[
                                    "archived_candidate_step"
                                ],

                            tool_metadata=
                                worker.functions,
                        )
                    )

                    critic = call_responses(
                        client,

                        role=
                            "frozen_critic",

                        benchmark=
                            "BFCL",

                        instance_id=
                            branch[
                                "instance_id"
                            ],

                        step_index=
                            next_step_index,

                        input_items=
                            critic_input,

                        compute_rows=
                            compute_rows,
                    )

                    critique = (
                        critic.output_text
                        or ""
                    )

                    if not critique.strip():
                        raise RuntimeError(
                            "EMPTY_BFCL_V2_CRITIQUE"
                        )

                    refiner_input = (
                        make_component_input(
                            refiner_prompt,

                            current_history=
                                current_history,

                            archived_candidate_step=
                                desc[
                                    "archived_candidate_step"
                                ],

                            critique=
                                critique,

                            tool_metadata=
                                worker.functions,
                        )
                    )

                    candidate_kind = desc[
                        "candidate_kind"
                    ]

                    response = (
                        call_responses(
                            client,

                            role=
                                "frozen_refiner",

                            benchmark=
                                "BFCL",

                            instance_id=
                                branch[
                                    "instance_id"
                                ],

                            step_index=
                                next_step_index,

                            input_items=
                                refiner_input,

                            compute_rows=
                                compute_rows,

                            tools=(
                                state[
                                    "tools"
                                ]
                                if candidate_kind
                                == "tool_call"
                                else None
                            ),

                            requested_temperature=
                                0.2,
                        )
                    )

                    state[
                        "messages"
                    ].extend(
                        list(
                            response.output
                        )
                    )

                    calls = (
                        extract_function_calls(
                            response
                        )
                    )

                    interventions.append(
                        {
                            "step_index":
                                next_step_index,

                            "operator":
                                "V_refine",

                            "critic_output":
                                critique,
                        }
                    )

                    if calls:
                        model_responses = [
                            {
                                call.name:
                                    call.arguments
                            }
                            for call in calls
                        ]

                        official_calls = (
                            state[
                                "convert_to_function_call"
                            ](
                                model_responses
                            )
                        )

                        normalized_calls = [
                            {
                                "call_id":
                                    call.call_id,

                                "name":
                                    call.name,

                                "arguments":
                                    call.arguments,
                            }
                            for call in calls
                        ]

                        bfcl_apply_function_calls_v2(
                            branch=
                                branch,

                            state=
                                state,

                            trace_turn=
                                trace_turn,

                            step_index=
                                next_step_index,

                            function_calls=
                                normalized_calls,

                            official_calls=
                                official_calls,

                            source=
                                "refined_intervention",
                        )

                        round_terminated = False

                    else:
                        text = (
                            response.output_text
                            or ""
                        )

                        if not text.strip():
                            raise RuntimeError(
                                "BFCL_V2_REFINER_EMPTY_STEP"
                            )

                        trace_turn[
                            "model_steps"
                        ].append(
                            {
                                "step_index":
                                    next_step_index,

                                "source":
                                    "refined_intervention",

                                "terminal_text":
                                    text,

                                "function_calls":
                                    [],
                            }
                        )

                        round_terminated = True

                elif operator == "V_oracle":
                    key = (
                        "BFCL",
                        branch[
                            "instance_id"
                        ],
                        next_step_index,
                    )

                    if key not in oracle_index:
                        raise RuntimeError(
                            "BFCL_ORACLE_ROW_MISSING="
                            + repr(key)
                        )

                    oracle_row = (
                        oracle_index[
                            key
                        ]
                    )

                    payload = (
                        oracle_row[
                            "patch_operation"
                        ][
                            "replacement_payload"
                        ]
                    )

                    if not isinstance(
                        payload,
                        list,
                    ):
                        raise RuntimeError(
                            "BFCL_ORACLE_PAYLOAD_NOT_LIST="
                            + repr(key)
                        )

                    normalized_calls = []

                    for ordinal, raw_call in enumerate(
                        payload
                    ):
                        parsed = (
                            parse_bfcl_raw_function_call(
                                raw_call
                            )
                        )

                        call_id = (
                            "oracle_"
                            + hashlib.sha256(
                                (
                                    branch[
                                        "execution_id"
                                    ]
                                    + "|"
                                    + str(
                                        next_step_index
                                    )
                                    + "|"
                                    + str(ordinal)
                                ).encode()
                            ).hexdigest()[:24]
                        )

                        state[
                            "messages"
                        ].append(
                            {
                                "type":
                                    "function_call",

                                "call_id":
                                    call_id,

                                "name":
                                    parsed[
                                        "function_name"
                                    ],

                                "arguments":
                                    json.dumps(
                                        parsed[
                                            "arguments"
                                        ],
                                        separators=(
                                            ",",
                                            ":",
                                        ),
                                        ensure_ascii=False,
                                    ),
                            }
                        )

                        normalized_calls.append(
                            {
                                "call_id":
                                    call_id,

                                "name":
                                    parsed[
                                        "function_name"
                                    ],

                                "arguments":
                                    json.dumps(
                                        parsed[
                                            "arguments"
                                        ],
                                        separators=(
                                            ",",
                                            ":",
                                        ),
                                        ensure_ascii=False,
                                    ),
                            }
                        )

                    bfcl_apply_function_calls_v2(
                        branch=
                            branch,

                        state=
                            state,

                        trace_turn=
                            trace_turn,

                        step_index=
                            next_step_index,

                        function_calls=
                            normalized_calls,

                        official_calls=
                            payload,

                        source=
                            "oracle_intervention",
                    )

                    interventions.append(
                        {
                            "step_index":
                                next_step_index,

                            "operator":
                                "V_oracle",

                            "oracle_target":
                                oracle_row[
                                    "oracle_target"
                                ],
                        }
                    )

                    round_terminated = False

                else:
                    raise RuntimeError(
                        "BFCL_V2_UNKNOWN_OPERATOR="
                        + operator
                    )

            else:
                started = (
                    time.perf_counter()
                )

                response = (
                    client.responses.create(
                        model=MODEL,

                        input=
                            state[
                                "messages"
                            ],

                        tools=
                            state[
                                "tools"
                            ],

                        reasoning={
                            "effort":
                                REASONING_EFFORT,
                        },

                        max_output_tokens=
                            MAX_OUTPUT_TOKENS,

                        store=False,
                    )
                )

                record_response_call(
                    compute_rows,

                    "branch_continuation_generator",

                    "BFCL",

                    branch[
                        "instance_id"
                    ],

                    next_step_index,

                    response,

                    started,

                    None,

                    "PROVIDER_DEFAULT",

                    0,
                )

                state[
                    "messages"
                ].extend(
                    list(
                        response.output
                    )
                )

                calls = (
                    extract_function_calls(
                        response
                    )
                )

                if calls:
                    model_responses = [
                        {
                            call.name:
                                call.arguments
                        }
                        for call in calls
                    ]

                    official_calls = (
                        state[
                            "convert_to_function_call"
                        ](
                            model_responses
                        )
                    )

                    normalized_calls = [
                        {
                            "call_id":
                                call.call_id,

                            "name":
                                call.name,

                            "arguments":
                                call.arguments,
                        }
                        for call in calls
                    ]

                    bfcl_apply_function_calls_v2(
                        branch=
                            branch,

                        state=
                            state,

                        trace_turn=
                            trace_turn,

                        step_index=
                            next_step_index,

                        function_calls=
                            normalized_calls,

                        official_calls=
                            official_calls,

                        source=
                            "branch_continuation",
                    )

                    round_terminated = False

                else:
                    text = (
                        response.output_text
                        or ""
                    )

                    trace_turn[
                        "model_steps"
                    ].append(
                        {
                            "step_index":
                                next_step_index,

                            "source":
                                "branch_continuation",

                            "terminal_text":
                                text,

                            "function_calls":
                                [],
                        }
                    )

                    round_terminated = True

            next_step_index += 1

            if next_step_index > 64:
                raise RuntimeError(
                    "BFCL_V2_BRANCH_EXCEEDED_64_MODEL_STEPS"
                )

        applied = [
            int(x["step_index"])
            for x in interventions
        ]

        if applied != selected_steps:
            raise RuntimeError(
                "BFCL_SELECTED_STEPS_NOT_ALL_APPLIED="
                + branch[
                    "execution_id"
                ]
                + ":applied="
                + repr(applied)
                + ":expected="
                + repr(
                    selected_steps
                )
            )

        state[
            "bfcl_mod"
        ] = bfcl_mod

        z, evaluator_result = (
            bfcl_terminal_utility(
                branch,
                state,
            )
        )

        return {
            "execution_id":
                branch[
                    "execution_id"
                ],

            "benchmark":
                "BFCL",

            "instance_id":
                branch[
                    "instance_id"
                ],

            "intervention_operator":
                branch[
                    "intervention_operator"
                ],

            "selected_steps_chronological":
                selected_steps,

            "exact_restoration_certified":
                True,

            "approximate_restoration":
                False,

            "intervention_records":
                interventions,

            "terminal_outcome_Z":
                z,

            "terminal_evaluator_result":
                evaluator_result,

            "trace_turns":
                state[
                    "trace_turns"
                ],

            "compute_rows":
                compute_rows,

            "status":
                "PASS",
        }

    finally:
        worker.close()


def execute_tool_branch_v2(
    branch,
    branch_descriptors,
    oracle_index,
    tool_mod,
    client,
):
    selected_steps = [
        int(x)
        for x in branch[
            "selected_steps_chronological"
        ]
    ]

    selected_set = set(
        selected_steps
    )

    desc_by_step = {
        int(desc["step_index"]):
            desc
        for desc in branch_descriptors
    }

    first_desc = desc_by_step[
        selected_steps[0]
    ]

    binding = (
        toolalpaca_authority_binding(
            first_desc
        )
    )

    pre_rows = load_jsonl(
        tool_mod.PRE_PATH
    )

    row = find_row(
        pre_rows,
        branch[
            "instance_id"
        ],
    )

    tools, op_lookup = (
        tool_mod.build_tools(
            row[
                "documentation"
            ]
        )
    )

    history = [
        {
            "role":
                "user",

            "content":
                row[
                    "instruction"
                ],
        }
    ]

    actions = []
    interventions = []
    compute_rows = []
    final_answer = ""

    contract = json.loads(
        REFINE_CONTRACT.read_text(
            encoding="utf-8"
        )
    )

    amendment = json.loads(
        REFINE_AMENDMENT.read_text(
            encoding="utf-8"
        )
    )

    critic_prompt = (
        contract[
            "critic"
        ][
            "prompt"
        ]
    )

    refiner_prompt = (
        amendment[
            "refiner"
        ][
            "prompt"
        ]
    )

    simulator_freeze = json.loads(
        tool_mod.FREEZE_PATH.read_text(
            encoding="utf-8"
        )
    )

    simulator_template = Template(
        tool_mod.SIMULATOR_PROMPT_PATH.read_text(
            encoding="utf-8"
        )
    )

    def apply_tool_calls(
        call_rows,
        step_index,
    ):
        for call_row in call_rows:
            name = call_row[
                "name"
            ]

            arguments = call_row[
                "arguments"
            ]

            call_id = call_row[
                "call_id"
            ]

            if name not in op_lookup:
                observation = (
                    "Status Code: 404. "
                    "Response: "
                    '{"message":"Function not found."}'
                )

                status_code = 404

                simulator_record = {
                    "simulator_called":
                        False,

                    "reason":
                        "unknown_function",
                }

            else:
                request_text = (
                    tool_mod.build_request(
                        row[
                            "api_name"
                        ],

                        op_lookup[
                            name
                        ],

                        arguments,
                    )
                )

                simulator_prompt = (
                    simulator_template
                    .safe_substitute(
                        Name=
                            row[
                                "api_name"
                            ],

                        Documentation=
                            row[
                                "documentation"
                            ],

                        Request=
                            request_text,
                    )
                )

                started = (
                    time.perf_counter()
                )

                sim_response = (
                    client.chat.completions.create(
                        model=
                            simulator_freeze[
                                "model"
                            ],

                        messages=[
                            {
                                "role":
                                    "user",

                                "content":
                                    simulator_prompt,
                            }
                        ],

                        temperature=float(
                            simulator_freeze[
                                "temperature"
                            ]
                        ),

                        top_p=float(
                            simulator_freeze[
                                "top_p"
                            ]
                        ),

                        n=int(
                            simulator_freeze[
                                "n"
                            ]
                        ),

                        reasoning_effort=
                            simulator_freeze[
                                "reasoning_effort"
                            ],
                    )
                )

                sim_usage = (
                    tool_mod.chat_usage(
                        sim_response
                    )
                )

                raw = (
                    sim_response
                    .choices[0]
                    .message
                    .content
                    or ""
                )

                (
                    status_code,
                    response_body,
                ) = (
                    tool_mod
                    .parse_simulator_output(
                        raw
                    )
                )

                observation = (
                    "Status Code: "
                    + str(
                        status_code
                    )
                    + ". Response: "
                    + json.dumps(
                        response_body,
                        ensure_ascii=False,
                    )
                )

                compute_rows.append(
                    {
                        "call_id":
                            hashlib.sha256(
                                (
                                    "tool_simulator|"
                                    + branch[
                                        "execution_id"
                                    ]
                                    + "|"
                                    + str(
                                        step_index
                                    )
                                    + "|"
                                    + str(
                                        len(
                                            actions
                                        )
                                    )
                                ).encode()
                            ).hexdigest(),

                        "call_role":
                            "environment_simulator",

                        "benchmark":
                            "ToolAlpaca",

                        "instance_id":
                            branch[
                                "instance_id"
                            ],

                        "step_index":
                            step_index,

                        "model_id":
                            simulator_freeze[
                                "model"
                            ],

                        "reasoning_effort":
                            simulator_freeze[
                                "reasoning_effort"
                            ],

                        "requested_temperature":
                            simulator_freeze[
                                "temperature"
                            ],

                        "effective_temperature_status":
                            "FROZEN_SIMULATOR_PARAMETER",

                        "input_tokens":
                            sim_usage[
                                "input_tokens"
                            ],

                        "output_tokens":
                            sim_usage[
                                "output_tokens"
                            ],

                        "total_tokens":
                            sim_usage[
                                "total_tokens"
                            ],

                        "latency":
                            time.perf_counter()
                            - started,

                        "retry_count":
                            0,

                        "response_id":
                            None,

                        "wall_clock_seconds":
                            time.time(),
                    }
                )

                simulator_record = {
                    "simulator_called":
                        True,

                    "model":
                        simulator_freeze[
                            "model"
                        ],

                    "temperature":
                        simulator_freeze[
                            "temperature"
                        ],

                    "top_p":
                        simulator_freeze[
                            "top_p"
                        ],

                    "request":
                        request_text,

                    "raw_output":
                        raw,
                }

            history.append(
                {
                    "type":
                        "function_call_output",

                    "call_id":
                        call_id,

                    "output":
                        observation,
                }
            )

            actions.append(
                {
                    "action_index":
                        len(actions)
                        + 1,

                    "turn_index":
                        step_index,

                    "function_name":
                        name,

                    "arguments":
                        arguments,

                    "call_id":
                        call_id,

                    "status_code":
                        status_code,

                    "observation":
                        observation,

                    "simulator":
                        simulator_record,
                }
            )

    step_index = 1

    while step_index <= 12:
        is_selected = (
            step_index
            in selected_set
        )

        operator = branch[
            "intervention_operator"
        ]

        if is_selected:
            if operator == "V_refine":
                desc = desc_by_step[
                    step_index
                ]

                current_history = (
                    runtime_history_json(
                        history
                    )
                )

                critic_input = (
                    make_component_input(
                        critic_prompt,

                        current_history=
                            current_history,

                        archived_candidate_step=
                            desc[
                                "archived_candidate_step"
                            ],

                        tool_metadata=
                            row[
                                "documentation"
                            ],
                    )
                )

                critic = call_responses(
                    client,

                    role=
                        "frozen_critic",

                    benchmark=
                        "ToolAlpaca",

                    instance_id=
                        branch[
                            "instance_id"
                        ],

                    step_index=
                        step_index,

                    input_items=
                        critic_input,

                    compute_rows=
                        compute_rows,
                )

                critique = (
                    critic.output_text
                    or ""
                )

                if not critique.strip():
                    raise RuntimeError(
                        "EMPTY_TOOLALPACA_V2_CRITIQUE"
                    )

                refiner_input = (
                    make_component_input(
                        refiner_prompt,

                        current_history=
                            current_history,

                        archived_candidate_step=
                            desc[
                                "archived_candidate_step"
                            ],

                        critique=
                            critique,

                        tool_metadata=
                            row[
                                "documentation"
                            ],
                    )
                )

                response = call_responses(
                    client,

                    role=
                        "frozen_refiner",

                    benchmark=
                        "ToolAlpaca",

                    instance_id=
                        branch[
                            "instance_id"
                        ],

                    step_index=
                        step_index,

                    input_items=
                        refiner_input,

                    compute_rows=
                        compute_rows,

                    tools=
                        tools,

                    requested_temperature=
                        0.2,
                )

                history.extend(
                    list(
                        response.output
                    )
                )

                interventions.append(
                    {
                        "step_index":
                            step_index,

                        "operator":
                            "V_refine",

                        "critic_output":
                            critique,
                    }
                )

                calls = (
                    extract_function_calls(
                        response
                    )
                )

                if not calls:
                    final_answer = (
                        response.output_text
                        or ""
                    )

                    break

                call_rows = []

                for call in calls:
                    try:
                        arguments = json.loads(
                            call.arguments
                        )

                    except Exception:
                        arguments = {}

                    call_rows.append(
                        {
                            "name":
                                call.name,

                            "arguments":
                                arguments,

                            "call_id":
                                call.call_id,
                        }
                    )

                apply_tool_calls(
                    call_rows,
                    step_index,
                )

            elif operator == "V_oracle":
                key = (
                    "ToolAlpaca",
                    branch[
                        "instance_id"
                    ],
                    step_index,
                )

                if key not in oracle_index:
                    raise RuntimeError(
                        "TOOLALPACA_ORACLE_ROW_MISSING="
                        + repr(key)
                    )

                oracle_row = (
                    oracle_index[
                        key
                    ]
                )

                payload = (
                    oracle_row[
                        "patch_operation"
                    ][
                        "replacement_payload"
                    ]
                )

                name = payload[
                    "function_name"
                ]

                arguments_raw = payload[
                    "arguments"
                ]

                if isinstance(
                    arguments_raw,
                    str,
                ):
                    arguments = json.loads(
                        arguments_raw
                    )

                else:
                    arguments = dict(
                        arguments_raw
                    )

                call_id = (
                    "oracle_"
                    + hashlib.sha256(
                        (
                            branch[
                                "execution_id"
                            ]
                            + "|"
                            + str(
                                step_index
                            )
                        ).encode()
                    ).hexdigest()[:24]
                )

                history.append(
                    {
                        "type":
                            "function_call",

                        "call_id":
                            call_id,

                        "name":
                            name,

                        "arguments":
                            json.dumps(
                                arguments,
                                separators=(
                                    ",",
                                    ":",
                                ),
                                ensure_ascii=False,
                            ),
                    }
                )

                apply_tool_calls(
                    [
                        {
                            "name":
                                name,

                            "arguments":
                                arguments,

                            "call_id":
                                call_id,
                        }
                    ],
                    step_index,
                )

                interventions.append(
                    {
                        "step_index":
                            step_index,

                        "operator":
                            "V_oracle",

                        "oracle_target":
                            oracle_row[
                                "oracle_target"
                            ],
                    }
                )

            else:
                raise RuntimeError(
                    "TOOLALPACA_V2_UNKNOWN_OPERATOR="
                    + operator
                )

        else:
            response = call_responses(
                client,

                role=
                    "branch_continuation_generator",

                benchmark=
                    "ToolAlpaca",

                instance_id=
                    branch[
                        "instance_id"
                    ],

                step_index=
                    step_index,

                input_items=
                    history,

                compute_rows=
                    compute_rows,

                tools=
                    tools,
            )

            history.extend(
                list(
                    response.output
                )
            )

            calls = (
                extract_function_calls(
                    response
                )
            )

            if not calls:
                final_answer = (
                    response.output_text
                    or ""
                )

                break

            call_rows = []

            for call in calls:
                try:
                    arguments = json.loads(
                        call.arguments
                    )

                except Exception:
                    arguments = {}

                call_rows.append(
                    {
                        "name":
                            call.name,

                        "arguments":
                            arguments,

                        "call_id":
                            call.call_id,
                    }
                )

            apply_tool_calls(
                call_rows,
                step_index,
            )

        step_index += 1

    if not final_answer:
        if (
            step_index > 12
        ):
            raise RuntimeError(
                "TOOLALPACA_V2_EXCEEDED_12_AGENT_TURNS"
            )

    applied = [
        int(x["step_index"])
        for x in interventions
    ]

    if applied != selected_steps:
        raise RuntimeError(
            "TOOLALPACA_SELECTED_STEPS_NOT_ALL_APPLIED="
            + branch[
                "execution_id"
            ]
            + ":applied="
            + repr(applied)
            + ":expected="
            + repr(
                selected_steps
            )
        )

    standard_answer = ""

    for i, ans in enumerate(
        binding[
            "golden_answers"
        ]
    ):
        standard_answer += (
            f"{i + 1}. Function: "
            f"{ans['Action']}\n"
            "Parameters: "
            f"{ans['Action_Input']}\n"
        )

    solution = ""

    for i, action in enumerate(
        actions
    ):
        solution += (
            f"{i + 1}. Function: "
            f"{action['function_name']}\n"
            "Parameters: "
            + json.dumps(
                action[
                    "arguments"
                ],
                ensure_ascii=False,
            )
            + "\n"
            "Retruns: "
            + action[
                "observation"
            ]
            + "\n"
        )

    solution += (
        f"{len(actions) + 1}. "
        "Final Response: "
        + final_answer
    )

    terminal_contract = json.loads(
        TERMINAL_CONTRACT.read_text(
            encoding="utf-8"
        )
    )

    eval_prompt_path = Path(
        terminal_contract[
            "toolalpaca"
        ][
            "evaluation_prompt_path"
        ]
    )

    if (
        sha256_file(
            eval_prompt_path
        )
        != terminal_contract[
            "toolalpaca"
        ][
            "evaluation_prompt_sha256"
        ]
    ):
        raise RuntimeError(
            "TOOLALPACA_EVALUATION_PROMPT_HASH_MISMATCH"
        )

    eval_template = Template(
        eval_prompt_path.read_text(
            encoding="utf-8"
        )
    )

    judge_prompt = (
        eval_template.substitute(
            documentation=
                binding[
                    "api_info"
                ][
                    "NLDocumentation"
                ],

            instruction=
                binding[
                    "instruction"
                ],

            standard=
                standard_answer,

            solution=
                solution,
        )
    )

    judge = call_responses(
        client,

        role=
            "terminal_utility_evaluator",

        benchmark=
            "ToolAlpaca",

        instance_id=
            branch[
                "instance_id"
            ],

        step_index=None,

        input_items=[
            {
                "role":
                    "user",

                "content":
                    judge_prompt,
            }
        ],

        compute_rows=
            compute_rows,
    )

    judge_text = (
        judge.output_text
        or ""
    )

    results_text = (
        judge_text.split(
            "## Results",
            1,
        )[-1]
    )

    process_match = re.search(
        r"Process Correctness: (\w+)",
        results_text,
    )

    final_match = re.search(
        r"Final Response Correctness: (\w+)",
        results_text,
    )

    process_word = (
        process_match.group(1)
        if process_match
        else ""
    )

    final_word = (
        final_match.group(1)
        if final_match
        else ""
    )

    z = (
        1
        if (
            process_word == "Yes"
            and final_word == "Yes"
        )
        else 0
    )

    return {
        "execution_id":
            branch[
                "execution_id"
            ],

        "benchmark":
            "ToolAlpaca",

        "instance_id":
            branch[
                "instance_id"
            ],

        "intervention_operator":
            branch[
                "intervention_operator"
            ],

        "selected_steps_chronological":
            selected_steps,

        "exact_restoration_certified":
            True,

        "approximate_restoration":
            False,

        "intervention_records":
            interventions,

        "actions":
            actions,

        "final_answer":
            final_answer,

        "terminal_judge_output":
            judge_text,

        "process_correctness":
            process_word,

        "final_response_correctness":
            final_word,

        "terminal_outcome_Z":
            z,

        "compute_rows":
            compute_rows,

        "status":
            "PASS",
    }
