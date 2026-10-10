#!/usr/bin/env python3

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from openai import OpenAI


ROOT = Path("__DECOUPLE_ROOT__")

PRE = ROOT / (
    "10_PILOT/STEP1/02_INPUTS/PRE_ONLY/"
    "BFCL_PILOT25_PRE.jsonl"
)

REQUEST_TEMPLATE = ROOT / (
    "10_PILOT/STEP1/03_WORK/STEP1B_TRAJECTORY/"
    "BFCL_MODEL_ACTION_SMOKE/STEP1B2G_TERRA_REQUEST.json"
)

BFCL_ROOT = ROOT / (
    "10_PILOT/STEP1/02_INPUTS/RAW_AUTHORITY/BFCL/gorilla/"
    "berkeley-function-call-leaderboard"
)

BFCL_UTILS = BFCL_ROOT / (
    "bfcl_eval/model_handler/utils.py"
)

_BUNDLED_VENDOR_ROOT = Path(__file__).resolve().parents[1] / "vendor/bfcl_tool_conversion"
VENDOR_ROOT = (
    _BUNDLED_VENDOR_ROOT
    if _BUNDLED_VENDOR_ROOT.is_dir()
    else ROOT / (
        "10_PILOT/STEP1/01_CODE/STEP1B_TRAJECTORY/vendor/"
        "bfcl_tool_conversion"
    )
)

OUT_DIR = ROOT / (
    "10_PILOT/STEP1/04_OUTPUTS/STEP1B_TRAJECTORY/"
    "ARCHIVED_BASE/BFCL"
)

AUDIT_DIR = ROOT / (
    "10_PILOT/STEP1/06_AUDIT/STEP1B_TRAJECTORY/"
    "ARCHIVED_BASE/BFCL"
)

WORK_DIR = ROOT / (
    "10_PILOT/STEP1/03_WORK/STEP1B_TRAJECTORY/"
    "ARCHIVED_BASE/BFCL"
)

MODEL_ID = "gpt-5.6-terra"
REASONING_EFFORT = "medium"
MAX_OUTPUT_TOKENS = 2048

EXPECTED_REQUEST_TEMPLATE_SHA = (
    "122cc581cdf5608ce403c54de788e2c269f82990ef125ab33a04abc785a48153"
)

FORBIDDEN_FIELDS = {
    "path",
    "missed_function",
    "excluded_function",
    "possible_answer",
    "ground_truth",
    "correctness",
    "reward",
    "outcome",
    "oracle",
    "intervention_gain",
}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_json_bytes(obj):
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def load_jsonl(path):
    rows = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    return rows


def recursive_forbidden_keys(obj):
    found = []

    def walk(value, prefix=""):
        if isinstance(value, dict):
            for key, child in value.items():
                key_string = str(key)
                path = (
                    f"{prefix}.{key_string}"
                    if prefix
                    else key_string
                )

                if key_string in FORBIDDEN_FIELDS:
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


def extract_function_source(path, function_name):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == function_name
        ):
            lines = source.splitlines()
            return "\n".join(
                lines[node.lineno - 1:node.end_lineno]
            )

    raise RuntimeError(
        f"{function_name} not found in {path}"
    )


def load_official_convert_to_function_call():
    function_source = extract_function_source(
        BFCL_UTILS,
        "convert_to_function_call",
    )

    namespace = {
        "json": json,
        "re": re,
    }

    try:
        exec(
            function_source,
            namespace,
            namespace,
        )
    except NameError as exc:
        raise RuntimeError(
            "Official BFCL convert_to_function_call "
            "has an unresolved dependency. "
            "Do not substitute custom decode logic. "
            f"Original error: {exc}"
        )

    fn = namespace.get(
        "convert_to_function_call"
    )

    if fn is None:
        raise RuntimeError(
            "Failed to load official BFCL "
            "convert_to_function_call"
        )

    return fn, sha256_bytes(
        function_source.encode("utf-8")
    )


def model_dump_item(item):
    if hasattr(item, "model_dump"):
        return item.model_dump()

    raise RuntimeError(
        "Response output item cannot be serialized"
    )


def safe_usage(response):
    usage = getattr(response, "usage", None)

    if usage is None:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }

    return {
        "input_tokens": getattr(
            usage,
            "input_tokens",
            None,
        ),
        "output_tokens": getattr(
            usage,
            "output_tokens",
            None,
        ),
        "total_tokens": getattr(
            usage,
            "total_tokens",
            None,
        ),
    }


def call_model(client, messages, tools):
    started = time.perf_counter()

    response = client.responses.create(
        model=MODEL_ID,
        input=messages,
        tools=tools,
        reasoning={
            "effort": REASONING_EFFORT,
        },
        max_output_tokens=MAX_OUTPUT_TOKENS,
        store=False,
    )

    latency = (
        time.perf_counter()
        - started
    )

    returned_model = getattr(
        response,
        "model",
        None,
    )

    if returned_model != MODEL_ID:
        raise RuntimeError(
            "Returned model mismatch: "
            f"{returned_model} != {MODEL_ID}"
        )

    usage = safe_usage(response)

    if usage["total_tokens"] is None:
        raise RuntimeError(
            "Missing token usage"
        )

    model_responses = []
    tool_call_ids = []

    for item in response.output:
        if item.type == "function_call":
            model_responses.append(
                {
                    item.name:
                    item.arguments
                }
            )
            tool_call_ids.append(
                item.call_id
            )

    # Preserve BFCL/OpenAI Responses official chat-history semantics.
    # Do NOT model_dump response.output before feeding it to the next
    # Responses API call. The dumped representation contains response-only
    # fields such as `status` that are invalid as subsequent input items.
    history_items = list(response.output)

    return {
        "response": response,
        "model_responses": model_responses,
        "tool_call_ids": tool_call_ids,
        "history_items": history_items,
        "usage": usage,
        "latency": latency,
    }


def load_tool_conversion():
    sys.path.insert(
        0,
        str(VENDOR_ROOT),
    )

    from bfcl_openai_responses_tool_conversion import (
        GORILLA_TO_OPENAPI,
        ModelStyle,
        convert_to_tool,
    )

    return (
        GORILLA_TO_OPENAPI,
        ModelStyle,
        convert_to_tool,
    )



class BFCLDockerWorker:
    def __init__(self, row, namespace):
        worker_path = (
            "/workspace/DECOUPLE/"
            "10_PILOT/STEP1/01_CODE/"
            "STEP1B_TRAJECTORY/"
            "bfcl_docker_trajectory_worker.py"
        )

        self.proc = subprocess.Popen(
            [
                "docker",
                "run",
                "--rm",
                "-i",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "-v",
                (
                    "__DECOUPLE_ROOT__:"
                    "/workspace/DECOUPLE:ro"
                ),
                "-e",
                (
                    "PYTHONPATH="
                    "/workspace/DECOUPLE/"
                    "10_PILOT/STEP1/02_INPUTS/"
                    "RAW_AUTHORITY/BFCL/gorilla/"
                    "berkeley-function-call-leaderboard"
                ),
                "--tmpfs",
                (
                    "/workspace/DECOUPLE/"
                    "10_PILOT/STEP1/02_INPUTS/"
                    "RAW_AUTHORITY/BFCL/gorilla/"
                    "berkeley-function-call-leaderboard/"
                    ".file_locks:"
                    "rw,uid=1000,gid=1000,mode=700"
                ),
                "decouple-naacl-agentlab:0.1",
                "python",
                worker_path,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        init_response = self.request(
            {
                "command": "init",
                "row": row,
                "namespace": namespace,
            }
        )

        if init_response.get("status") != "PASS":
            raise RuntimeError(
                "BFCL Docker worker init failed"
            )

        self.question = init_response["question"]
        self.functions = init_response["functions"]

    def request(self, payload):
        if self.proc.poll() is not None:
            stderr = self.proc.stderr.read()
            raise RuntimeError(
                "BFCL Docker worker terminated: "
                + stderr
            )

        self.proc.stdin.write(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        self.proc.stdin.flush()

        line = self.proc.stdout.readline()

        if not line:
            stderr = self.proc.stderr.read()
            raise RuntimeError(
                "BFCL Docker worker returned no response: "
                + stderr
            )

        return json.loads(line)

    def execute(self, calls):
        response = self.request(
            {
                "command": "execute",
                "calls": calls,
            }
        )

        if response.get("status") != "PASS":
            raise RuntimeError(
                "BFCL Docker execution failed"
            )

        return response["execution_results"]

    def close(self):
        if self.proc.poll() is None:
            try:
                self.request(
                    {"command": "close"}
                )
            finally:
                self.proc.stdin.close()
                self.proc.wait()

        if self.proc.returncode != 0:
            stderr = self.proc.stderr.read()
            raise RuntimeError(
                "BFCL Docker worker exited nonzero: "
                + stderr
            )


def main():
    if not os.environ.get(
        "OPENAI_API_KEY"
    ):
        raise RuntimeError(
            "OPENAI_API_KEY is not set"
        )

    if (
        sha256_file(
            REQUEST_TEMPLATE
        )
        != EXPECTED_REQUEST_TEMPLATE_SHA
    ):
        raise RuntimeError(
            "Frozen request template hash mismatch"
        )

    (
        GORILLA_TO_OPENAPI,
        ModelStyle,
        convert_to_tool,
    ) = load_tool_conversion()

    (
        convert_to_function_call,
        decoder_source_sha,
    ) = load_official_convert_to_function_call()

    rows = load_jsonl(PRE)

    if len(rows) != 25:
        raise RuntimeError(
            f"Expected 25 BFCL PRE rows, got {len(rows)}"
        )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    WORK_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    client = OpenAI()

    index_rows = []
    ledger_rows = []

    for trajectory_number, row in enumerate(
        rows,
        start=1,
    ):
        forbidden = recursive_forbidden_keys(
            row
        )

        if forbidden:
            raise RuntimeError(
                "Forbidden PRE fields found: "
                + repr(forbidden)
            )

        namespace = (
            "decouple_base_"
            + row["selection_hash"][:16]
        )

        worker = BFCLDockerWorker(
            row,
            namespace,
        )

        tools = convert_to_tool(
            worker.functions,
            GORILLA_TO_OPENAPI,
            ModelStyle.OPENAI_RESPONSES,
        )

        messages = []

        trajectory = {
            "project": "DECOUPLE",
            "stage": "10_PILOT",
            "step": "STEP1",
            "artifact_type": "archived_base_trajectory",
            "benchmark": "BFCL",
            "instance_id": row["instance_id"],
            "category": row["category"],
            "selection_hash": row["selection_hash"],
            "model_id": MODEL_ID,
            "reasoning_effort": REASONING_EFFORT,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "scientific_base_trajectory": True,
            "turns": [],
        }

        total_input = 0
        total_output = 0
        total_tokens = 0
        total_latency = 0.0
        call_count = 0
        action_count = 0

        for round_idx, user_turn in enumerate(
            worker.question
        ):
            user_turn_copy = [
                dict(message)
                for message in user_turn
            ]

            for message in user_turn_copy:
                if (
                    message.get("role")
                    == "system"
                ):
                    message["role"] = (
                        "developer"
                    )

            messages.extend(
                user_turn_copy
            )

            round_record = {
                "round_index": round_idx,
                "user_messages":
                    user_turn_copy,
                "model_steps": [],
            }

            max_actions_this_round = 32

            for local_step in range(
                max_actions_this_round
            ):
                result = call_model(
                    client,
                    messages,
                    tools,
                )

                call_count += 1

                usage = result["usage"]

                total_input += (
                    usage["input_tokens"]
                )
                total_output += (
                    usage["output_tokens"]
                )
                total_tokens += (
                    usage["total_tokens"]
                )
                total_latency += (
                    result["latency"]
                )

                response = result["response"]

                messages.extend(
                    result["history_items"]
                )

                ledger_rows.append(
                    {
                        "benchmark": "BFCL",
                        "instance_id":
                            row["instance_id"],
                        "trajectory_id":
                            row["selection_hash"],
                        "round_index":
                            round_idx,
                        "local_step":
                            local_step,
                        "model_id":
                            MODEL_ID,
                        "input_tokens":
                            usage["input_tokens"],
                        "output_tokens":
                            usage["output_tokens"],
                        "total_tokens":
                            usage["total_tokens"],
                        "reasoning_effort":
                            REASONING_EFFORT,
                        "max_output_tokens":
                            MAX_OUTPUT_TOKENS,
                        "latency_seconds":
                            result["latency"],
                        "retry_count": 0,
                        "cache_status":
                            "not_used",
                        "response_id":
                            response.id,
                    }
                )

                if (
                    not
                    result["model_responses"]
                ):
                    round_record[
                        "model_steps"
                    ].append(
                        {
                            "response_id":
                                response.id,
                            "terminal_text":
                                response.output_text,
                            "function_calls":
                                [],
                            "execution_results":
                                [],
                        }
                    )
                    break

                executable_calls = (
                    convert_to_function_call(
                        result[
                            "model_responses"
                        ]
                    )
                )

                if (
                    len(executable_calls)
                    != len(
                        result[
                            "tool_call_ids"
                        ]
                    )
                ):
                    raise RuntimeError(
                        "BFCL decode count does not "
                        "match function call IDs"
                    )

                execution_results = (
                    worker.execute(
                        executable_calls
                    )
                )

                if (
                    len(execution_results)
                    != len(executable_calls)
                ):
                    raise RuntimeError(
                        "Executor result count mismatch"
                    )

                action_count += len(
                    executable_calls
                )

                function_outputs = []

                for (
                    execution_result,
                    call_id,
                ) in zip(
                    execution_results,
                    result[
                        "tool_call_ids"
                    ],
                ):
                    output_message = {
                        "type":
                            "function_call_output",
                        "call_id":
                            call_id,
                        "output":
                            execution_result,
                    }

                    messages.append(
                        output_message
                    )

                    function_outputs.append(
                        output_message
                    )

                round_record[
                    "model_steps"
                ].append(
                    {
                        "response_id":
                            response.id,
                        "function_calls":
                            executable_calls,
                        "execution_results":
                            execution_results,
                        "function_call_outputs":
                            function_outputs,
                    }
                )

            else:
                raise RuntimeError(
                    "Exceeded 32 model action cycles "
                    f"for {row['instance_id']} "
                    f"round {round_idx}"
                )

            trajectory["turns"].append(
                round_record
            )

        worker.close()

        trajectory["summary"] = {
            "model_call_count":
                call_count,
            "tool_action_count":
                action_count,
            "input_tokens":
                total_input,
            "output_tokens":
                total_output,
            "total_tokens":
                total_tokens,
            "latency_seconds":
                total_latency,
        }

        trajectory_path = (
            OUT_DIR
            / (
                f"{trajectory_number:03d}_"
                f"{row['instance_id']}.json"
            )
        )

        trajectory_path.write_text(
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
                trajectory_path
            )
        )

        index_rows.append(
            {
                "trajectory_number":
                    trajectory_number,
                "instance_id":
                    row["instance_id"],
                "category":
                    row["category"],
                "selection_hash":
                    row["selection_hash"],
                "trajectory_path":
                    str(
                        trajectory_path.relative_to(
                            ROOT
                        )
                    ),
                "trajectory_sha256":
                    trajectory_sha,
                "model_call_count":
                    call_count,
                "tool_action_count":
                    action_count,
                "total_tokens":
                    total_tokens,
            }
        )

        print(
            "DONE "
            f"{trajectory_number}/25 "
            f"{row['instance_id']} "
            f"calls={call_count} "
            f"actions={action_count} "
            f"tokens={total_tokens}"
        )

    index_path = (
        OUT_DIR
        / "BFCL_PILOT25_TRAJECTORY_INDEX.json"
    )

    index_path.write_text(
        json.dumps(
            index_rows,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    ledger_path = (
        AUDIT_DIR
        / "BFCL_PILOT25_COMPUTE_LEDGER.json"
    )

    ledger_path.write_text(
        json.dumps(
            ledger_rows,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "status": "PASS",
        "benchmark": "BFCL",
        "trajectory_count":
            len(index_rows),
        "scientific_base_trajectory_count":
            len(index_rows),
        "model_id":
            MODEL_ID,
        "reasoning_effort":
            REASONING_EFFORT,
        "max_output_tokens":
            MAX_OUTPUT_TOKENS,
        "bfcl_revision":
            "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8",
        "pre_sha256":
            sha256_file(PRE),
        "bfcl_utils_sha256":
            sha256_file(
                BFCL_UTILS
            ),
        "official_decoder_source_sha256":
            decoder_source_sha,
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
        "ground_truth_used":
            False,
        "possible_answer_used":
            False,
    }

    manifest_path = (
        AUDIT_DIR
        / "BFCL_PILOT25_ARCHIVE_MANIFEST.json"
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
        "===== BFCL PILOT25 ARCHIVED BASE TRAJECTORIES ====="
    )
    print("STATUS=PASS")
    print("TRAJECTORY_COUNT=25")
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
    print("GROUND_TRUTH_USED=NO")
    print("POSSIBLE_ANSWER_USED=NO")


if __name__ == "__main__":
    main()
