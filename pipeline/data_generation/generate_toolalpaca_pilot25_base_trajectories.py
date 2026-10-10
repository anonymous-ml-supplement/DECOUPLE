#!/usr/bin/env python3

import hashlib
import json
import re
import time
from pathlib import Path
from string import Template
from urllib.parse import urlencode

from openai import OpenAI


ROOT = Path("__DECOUPLE_ROOT__")

PRE_PATH = (
    ROOT
    / "10_PILOT/STEP1/02_INPUTS/PRE_ONLY/"
      "TOOLALPACA_PILOT25_EXECUTION_PRE.jsonl"
)

FREEZE_PATH = (
    ROOT
    / "10_PILOT/STEP1/03_CONFIG/"
      "STEP1B_TRAJECTORY/"
      "TOOLALPACA_SIMULATOR_FREEZE.json"
)

SIMULATOR_PROMPT_PATH = (
    ROOT
    / "10_PILOT/STEP1/02_INPUTS/"
      "RAW_AUTHORITY/TOOLALPACA/"
      "ToolAlpaca/prompts/Simulator.txt"
)

OUT_DIR = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1B_TRAJECTORY/ARCHIVED_BASE/"
      "TOOLALPACA"
)

AUDIT_DIR = (
    ROOT
    / "10_PILOT/STEP1/06_AUDIT/"
      "STEP1B_TRAJECTORY/ARCHIVED_BASE/"
      "TOOLALPACA"
)

AGENT_MODEL = "gpt-5.6-terra"
AGENT_REASONING_EFFORT = "medium"
AGENT_MAX_OUTPUT_TOKENS = 2048

MAX_AGENT_TURNS = 12

EXPECTED_SIMULATOR = (
    "gpt-5.4-mini-2026-03-17"
)

EXPECTED_FREEZE_SHA256 = (
    "5d453fbf5afe7a043fbecd0479b4b2baa079dad1fca98f513f66c83ec47182c2"
)

FORBIDDEN_KEYS = {
    "golden_answers",
    "golden_answer",
    "instances",
    "possible_answer",
    "ground_truth",
    "correctness",
    "reward",
    "outcome",
    "oracle",
    "intervention_gain",
    "process_correctness",
    "final_response_correctness",
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


def recursive_forbidden(obj):
    found = []

    def walk(value, prefix="root"):
        if isinstance(value, dict):
            for k, v in value.items():
                p = f"{prefix}.{k}"

                if str(k).lower() in FORBIDDEN_KEYS:
                    found.append(p)

                walk(v, p)

        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, f"{prefix}[{i}]")

    walk(obj)

    return found


def resolve_ref(spec, value):
    if not isinstance(value, dict):
        return value

    if "$ref" not in value:
        return value

    ref = value["$ref"]

    if not ref.startswith("#/"):
        return value

    target = spec

    for part in ref[2:].split("/"):
        target = target[part]

    return resolve_ref(spec, target)


def normalize_schema(spec, schema):
    schema = resolve_ref(spec, schema)

    if not isinstance(schema, dict):
        return {}

    out = {}

    for key in (
        "type",
        "description",
        "enum",
        "format",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "default",
    ):
        if key in schema:
            out[key] = schema[key]

    if "properties" in schema:
        out["type"] = "object"

        out["properties"] = {
            k: normalize_schema(
                spec,
                v,
            )
            for k, v in schema[
                "properties"
            ].items()
        }

        if schema.get("required"):
            out["required"] = list(
                schema["required"]
            )

    if "items" in schema:
        out["type"] = "array"
        out["items"] = normalize_schema(
            spec,
            schema["items"],
        )

    if not out:
        out["type"] = "string"

    return out


def build_tools(documentation):
    spec = json.loads(documentation)

    tools = []
    op_lookup = {}

    for path, path_obj in spec.get(
        "paths",
        {},
    ).items():
        if not isinstance(
            path_obj,
            dict,
        ):
            continue

        for method, op in path_obj.items():
            method_lower = method.lower()

            if method_lower not in {
                "get",
                "post",
                "put",
                "delete",
                "patch",
            }:
                continue

            if not isinstance(op, dict):
                continue

            name = op.get(
                "operationId"
            )

            if not name:
                continue

            properties = {}
            required = []

            parameters = []

            parameters.extend(
                path_obj.get(
                    "parameters",
                    [],
                )
            )

            parameters.extend(
                op.get(
                    "parameters",
                    [],
                )
            )

            for param in parameters:
                param = resolve_ref(
                    spec,
                    param,
                )

                pname = param.get(
                    "name"
                )

                if not pname:
                    continue

                pschema = normalize_schema(
                    spec,
                    param.get(
                        "schema",
                        {},
                    ),
                )

                if param.get(
                    "description"
                ):
                    pschema[
                        "description"
                    ] = param[
                        "description"
                    ]

                properties[
                    pname
                ] = pschema

                if param.get(
                    "required",
                    False,
                ):
                    required.append(
                        pname
                    )

            body = op.get(
                "requestBody"
            )

            if body:
                body = resolve_ref(
                    spec,
                    body,
                )

                content = body.get(
                    "content",
                    {},
                )

                json_body = content.get(
                    "application/json",
                    {},
                )

                body_schema = (
                    normalize_schema(
                        spec,
                        json_body.get(
                            "schema",
                            {},
                        ),
                    )
                )

                if (
                    body_schema.get(
                        "type"
                    )
                    == "object"
                ):
                    for pname, pschema in (
                        body_schema.get(
                            "properties",
                            {},
                        ).items()
                    ):
                        properties[
                            pname
                        ] = pschema

                    required.extend(
                        body_schema.get(
                            "required",
                            []
                        )
                    )

            parameters_schema = {
                "type": "object",
                "properties":
                    properties,
                "additionalProperties":
                    False,
            }

            if required:
                parameters_schema[
                    "required"
                ] = sorted(
                    set(required)
                )

            tool = {
                "type": "function",
                "name": name,
                "description": op.get(
                    "description",
                    op.get(
                        "summary",
                        name,
                    ),
                ),
                "parameters":
                    parameters_schema,
                "strict": False,
            }

            tools.append(tool)

            op_lookup[name] = {
                "path":
                    path,
                "method":
                    method_lower,
                "operation":
                    op,
                "spec":
                    spec,
            }

    if not tools:
        raise RuntimeError(
            "No OpenAPI operations converted."
        )

    return tools, op_lookup


def build_request(
    api_name,
    operation_info,
    arguments,
):
    spec = operation_info[
        "spec"
    ]

    op = operation_info[
        "operation"
    ]

    method = operation_info[
        "method"
    ]

    path = operation_info[
        "path"
    ]

    servers = spec.get(
        "servers",
        [],
    )

    if servers:
        base_url = servers[0].get(
            "url",
            "",
        )
    else:
        base_url = (
            f"https://toolalpaca.local/"
            f"{api_name}"
        )

    base_url = base_url.rstrip("/")

    all_parameters = []

    path_obj = spec.get(
        "paths",
        {},
    ).get(
        path,
        {},
    )

    all_parameters.extend(
        path_obj.get(
            "parameters",
            [],
        )
    )

    all_parameters.extend(
        op.get(
            "parameters",
            [],
        )
    )

    location_by_name = {}

    for param in all_parameters:
        param = resolve_ref(
            spec,
            param,
        )

        if param.get("name"):
            location_by_name[
                param["name"]
            ] = param.get(
                "in",
                "query",
            )

    query = {}
    headers = {}
    body = {}

    rendered_path = path

    for key, value in arguments.items():
        location = location_by_name.get(
            key
        )

        if location == "path":
            rendered_path = (
                rendered_path.replace(
                    "{" + key + "}",
                    str(value),
                )
            )

        elif location == "header":
            headers[key] = value

        elif location == "query":
            query[key] = value

        else:
            body[key] = value

    url = (
        base_url
        + "/"
        + rendered_path.lstrip("/")
    )

    if query:
        url += "?" + urlencode(
            query,
            doseq=True,
        )

    header_text = " ".join(
        f'-H "{k}: {v}"'
        for k, v in headers.items()
    )

    body_text = ""

    if body:
        body_text = (
            "-d '"
            + json.dumps(
                body,
                ensure_ascii=False,
            )
            + "'"
        )

    request = (
        f"curl -X {method.upper()} "
        f"{header_text} "
        f"{body_text} "
        f"{url}"
    ).strip()

    request = re.sub(
        r"\s+",
        " ",
        request,
    )

    return request


def parse_simulator_output(text):
    status_match = re.search(
        r"Status Code:\s*(\d+)",
        text,
        flags=re.IGNORECASE,
    )

    if not status_match:
        return 500, {
            "simulator_parse_error":
                True,
            "raw_response":
                text,
        }

    status_code = int(
        status_match.group(1)
    )

    response_match = re.search(
        r"Response:\s*(.*?)(?:\n\s*Explanation:|\Z)",
        text,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not response_match:
        return status_code, {
            "simulator_parse_error":
                True,
            "raw_response":
                text,
        }

    response_text = (
        response_match
        .group(1)
        .strip()
    )

    try:
        response = json.loads(
            response_text
        )
    except Exception:
        response = {
            "response":
                response_text
        }

    return status_code, response


def response_usage(response):
    usage = getattr(
        response,
        "usage",
        None,
    )

    if usage is None:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    return {
        "input_tokens":
            int(
                getattr(
                    usage,
                    "input_tokens",
                    0,
                )
                or 0
            ),
        "output_tokens":
            int(
                getattr(
                    usage,
                    "output_tokens",
                    0,
                )
                or 0
            ),
        "total_tokens":
            int(
                getattr(
                    usage,
                    "total_tokens",
                    0,
                )
                or 0
            ),
    }


def chat_usage(response):
    usage = getattr(
        response,
        "usage",
        None,
    )

    if usage is None:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    return {
        "input_tokens":
            int(
                getattr(
                    usage,
                    "prompt_tokens",
                    0,
                )
                or 0
            ),
        "output_tokens":
            int(
                getattr(
                    usage,
                    "completion_tokens",
                    0,
                )
                or 0
            ),
        "total_tokens":
            int(
                getattr(
                    usage,
                    "total_tokens",
                    0,
                )
                or 0
            ),
    }


def add_usage(total, delta):
    for key in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ):
        total[key] += delta[key]


def main():
    if (
        sha256_file(FREEZE_PATH)
        != EXPECTED_FREEZE_SHA256
    ):
        raise RuntimeError(
            "ToolAlpaca simulator freeze "
            "hash mismatch."
        )

    freeze = json.loads(
        FREEZE_PATH.read_text(
            encoding="utf-8"
        )
    )

    simulator_model = freeze[
        "model"
    ]

    if (
        simulator_model
        != EXPECTED_SIMULATOR
    ):
        raise RuntimeError(
            "Unexpected simulator model: "
            + simulator_model
        )

    rows = [
        json.loads(line)
        for line in PRE_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    if len(rows) != 25:
        raise RuntimeError(
            f"Expected 25 rows, "
            f"got {len(rows)}"
        )

    forbidden = (
        recursive_forbidden(rows)
    )

    if forbidden:
        raise RuntimeError(
            "Forbidden PRE fields: "
            + repr(forbidden)
        )

    simulator_template = Template(
        SIMULATOR_PROMPT_PATH.read_text(
            encoding="utf-8"
        )
    )

    client = OpenAI()

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    index = []
    compute_rows = []

    aggregate_agent = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

    aggregate_simulator = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

    total_agent_calls = 0
    total_simulator_calls = 0
    total_actions = 0

    for position, row in enumerate(
        rows,
        start=1,
    ):
        tools, op_lookup = (
            build_tools(
                row["documentation"]
            )
        )

        history = [
            {
                "role": "user",
                "content":
                    row["instruction"],
            }
        ]

        actions = []
        assistant_turns = []

        agent_usage_total = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

        simulator_usage_total = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

        agent_calls = 0
        simulator_calls = 0

        final_answer = ""
        stop_reason = (
            "max_agent_turns"
        )

        started = time.time()

        for turn_index in range(
            1,
            MAX_AGENT_TURNS + 1,
        ):
            response = (
                client.responses.create(
                    model=AGENT_MODEL,
                    input=history,
                    tools=tools,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                    reasoning={
                        "effort":
                            AGENT_REASONING_EFFORT
                    },
                    max_output_tokens=(
                        AGENT_MAX_OUTPUT_TOKENS
                    ),
                    store=False,
                )
            )

            agent_calls += 1
            total_agent_calls += 1

            usage = response_usage(
                response
            )

            add_usage(
                agent_usage_total,
                usage,
            )

            add_usage(
                aggregate_agent,
                usage,
            )

            function_calls = [
                item
                for item in response.output
                if getattr(
                    item,
                    "type",
                    None,
                ) == "function_call"
            ]

            visible_text = (
                response.output_text
                or ""
            )

            assistant_turns.append(
                {
                    "turn_index":
                        turn_index,
                    "response_id":
                        response.id,
                    "visible_text":
                        visible_text,
                    "function_call_count":
                        len(
                            function_calls
                        ),
                    "usage":
                        usage,
                }
            )

            history.extend(
                list(
                    response.output
                )
            )

            if not function_calls:
                final_answer = (
                    visible_text
                )

                stop_reason = (
                    "assistant_final"
                )

                break

            for call in function_calls:
                name = call.name

                if name not in op_lookup:
                    observation = (
                        "Status Code: 404. "
                        "Response: "
                        '{"message":"Function '
                        'not found."}'
                    )

                    status_code = 404

                    simulator_record = {
                        "simulator_called":
                            False,
                        "reason":
                            "unknown_function",
                    }

                    arguments = {}

                else:
                    try:
                        arguments = (
                            json.loads(
                                call.arguments
                            )
                        )
                    except Exception:
                        arguments = {}

                    request_text = (
                        build_request(
                            row["api_name"],
                            op_lookup[name],
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

                    sim_response = (
                        client.chat.completions.create(
                            model=(
                                simulator_model
                            ),
                            messages=[
                                {
                                    "role":
                                        "user",
                                    "content":
                                        simulator_prompt,
                                }
                            ],
                            temperature=float(
                                freeze[
                                    "temperature"
                                ]
                            ),
                            top_p=float(
                                freeze[
                                    "top_p"
                                ]
                            ),
                            n=int(
                                freeze["n"]
                            ),
                            reasoning_effort=(
                                freeze[
                                    "reasoning_effort"
                                ]
                            ),
                        )
                    )

                    simulator_calls += 1
                    total_simulator_calls += 1

                    sim_usage = chat_usage(
                        sim_response
                    )

                    add_usage(
                        simulator_usage_total,
                        sim_usage,
                    )

                    add_usage(
                        aggregate_simulator,
                        sim_usage,
                    )

                    raw_simulator_text = (
                        sim_response
                        .choices[0]
                        .message
                        .content
                        or ""
                    )

                    (
                        status_code,
                        response_body,
                    ) = parse_simulator_output(
                        raw_simulator_text
                    )

                    observation = (
                        "Status Code: "
                        f"{status_code}. "
                        "Response: "
                        + json.dumps(
                            response_body,
                            ensure_ascii=False,
                        )
                    )

                    simulator_record = {
                        "simulator_called":
                            True,
                        "model":
                            simulator_model,
                        "temperature":
                            freeze[
                                "temperature"
                            ],
                        "top_p":
                            freeze[
                                "top_p"
                            ],
                        "request":
                            request_text,
                        "raw_output":
                            raw_simulator_text,
                        "usage":
                            sim_usage,
                    }

                history.append(
                    {
                        "type":
                            "function_call_output",
                        "call_id":
                            call.call_id,
                        "output":
                            observation,
                    }
                )

                action_index = (
                    len(actions) + 1
                )

                actions.append(
                    {
                        "action_index":
                            action_index,
                        "turn_index":
                            turn_index,
                        "function_name":
                            name,
                        "arguments":
                            arguments,
                        "call_id":
                            call.call_id,
                        "status_code":
                            status_code,
                        "observation":
                            observation,
                        "simulator":
                            simulator_record,
                    }
                )

                total_actions += 1

        elapsed = (
            time.time() - started
        )

        trajectory = {
            "project":
                "DECOUPLE",
            "stage":
                "10_PILOT",
            "step":
                "STEP1",
            "artifact_type":
                "archived_base_trajectory",
            "benchmark":
                "ToolAlpaca",
            "instance_id":
                row["instance_id"],
            "instruction":
                row["instruction"],
            "selection_hash":
                row["selection_hash"],
            "source_revision":
                row["source_revision"],
            "source_group_index":
                row[
                    "source_group_index"
                ],
            "source_instruction_index":
                row[
                    "source_instruction_index"
                ],
            "agent_model":
                AGENT_MODEL,
            "agent_reasoning_effort":
                AGENT_REASONING_EFFORT,
            "agent_max_output_tokens":
                AGENT_MAX_OUTPUT_TOKENS,
            "simulator_model":
                simulator_model,
            "simulator_temperature":
                freeze["temperature"],
            "simulator_top_p":
                freeze["top_p"],
            "simulator_role":
                "environment_response_synthesis_only",
            "actions":
                actions,
            "assistant_turns":
                assistant_turns,
            "final_answer":
                final_answer,
            "stop_reason":
                stop_reason,
            "agent_calls":
                agent_calls,
            "simulator_calls":
                simulator_calls,
            "action_count":
                len(actions),
            "agent_usage":
                agent_usage_total,
            "simulator_usage":
                simulator_usage_total,
            "all_in_tokens":
                (
                    agent_usage_total[
                        "total_tokens"
                    ]
                    + simulator_usage_total[
                        "total_tokens"
                    ]
                ),
            "wall_clock_seconds":
                elapsed,
            "posthoc_fields_used":
                False,
            "golden_answers_used":
                False,
            "evaluation_outputs_used":
                False,
        }

        output_path = (
            OUT_DIR
            / (
                f"{position:03d}_"
                f"{row['instance_id']}.json"
            )
        )

        output_path.write_text(
            json.dumps(
                trajectory,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        trajectory_sha = (
            sha256_file(
                output_path
            )
        )

        index.append(
            {
                "position":
                    position,
                "instance_id":
                    row["instance_id"],
                "action_count":
                    len(actions),
                "agent_calls":
                    agent_calls,
                "simulator_calls":
                    simulator_calls,
                "stop_reason":
                    stop_reason,
                "all_in_tokens":
                    trajectory[
                        "all_in_tokens"
                    ],
                "trajectory_path":
                    str(
                        output_path.relative_to(
                            ROOT
                        )
                    ),
                "trajectory_sha256":
                    trajectory_sha,
            }
        )

        compute_rows.append(
            {
                "instance_id":
                    row["instance_id"],
                "agent_calls":
                    agent_calls,
                "simulator_calls":
                    simulator_calls,
                "agent_usage":
                    agent_usage_total,
                "simulator_usage":
                    simulator_usage_total,
                "all_in_tokens":
                    trajectory[
                        "all_in_tokens"
                    ],
                "wall_clock_seconds":
                    elapsed,
            }
        )

        print(
            f"DONE {position}/25 "
            f"{row['instance_id']} "
            f"agent_calls={agent_calls} "
            f"sim_calls={simulator_calls} "
            f"actions={len(actions)} "
            f"tokens="
            f"{trajectory['all_in_tokens']}",
            flush=True,
        )

    index_path = (
        OUT_DIR
        / "TOOLALPACA_PILOT25_TRAJECTORY_INDEX.json"
    )

    index_path.write_text(
        json.dumps(
            index,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    ledger = {
        "benchmark":
            "ToolAlpaca",
        "instance_count":
            25,
        "agent_model":
            AGENT_MODEL,
        "simulator_model":
            simulator_model,
        "total_agent_calls":
            total_agent_calls,
        "total_simulator_calls":
            total_simulator_calls,
        "total_actions":
            total_actions,
        "agent_usage":
            aggregate_agent,
        "simulator_usage":
            aggregate_simulator,
        "total_all_in_tokens":
            (
                aggregate_agent[
                    "total_tokens"
                ]
                + aggregate_simulator[
                    "total_tokens"
                ]
            ),
        "instances":
            compute_rows,
    }

    ledger_path = (
        AUDIT_DIR
        / "TOOLALPACA_PILOT25_COMPUTE_LEDGER.json"
    )

    ledger_path.write_text(
        json.dumps(
            ledger,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "status":
            "PASS",
        "benchmark":
            "ToolAlpaca",
        "instance_count":
            25,
        "agent_model":
            AGENT_MODEL,
        "simulator_model":
            simulator_model,
        "simulator_role":
            "environment_response_synthesis_only",
        "simulator_freeze_sha256":
            sha256_file(
                FREEZE_PATH
            ),
        "execution_pre_sha256":
            sha256_file(
                PRE_PATH
            ),
        "simulator_prompt_sha256":
            sha256_file(
                SIMULATOR_PROMPT_PATH
            ),
        "trajectory_index_sha256":
            sha256_file(
                index_path
            ),
        "compute_ledger_sha256":
            sha256_file(
                ledger_path
            ),
        "posthoc_fields_used":
            False,
        "golden_answers_used":
            False,
        "evaluation_outputs_used":
            False,
    }

    manifest_path = (
        AUDIT_DIR
        / "TOOLALPACA_PILOT25_ARCHIVE_MANIFEST.json"
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
        "===== TOOLALPACA PILOT25 "
        "ARCHIVED BASE TRAJECTORIES ====="
    )
    print("STATUS=PASS")
    print("TRAJECTORY_COUNT=25")
    print(
        f"TOTAL_AGENT_CALLS="
        f"{total_agent_calls}"
    )
    print(
        f"TOTAL_SIMULATOR_CALLS="
        f"{total_simulator_calls}"
    )
    print(
        f"TOTAL_ACTIONS="
        f"{total_actions}"
    )
    print(
        "TOTAL_ALL_IN_TOKENS="
        + str(
            ledger[
                "total_all_in_tokens"
            ]
        )
    )
    print(
        "INDEX_SHA256="
        + sha256_file(
            index_path
        )
    )
    print(
        "COMPUTE_LEDGER_SHA256="
        + sha256_file(
            ledger_path
        )
    )
    print(
        "MANIFEST_SHA256="
        + sha256_file(
            manifest_path
        )
    )
    print("POSTHOC_FIELDS_USED=NO")
    print("GOLDEN_ANSWERS_USED=NO")
    print("EVALUATION_OUTPUTS_USED=NO")


if __name__ == "__main__":
    main()
