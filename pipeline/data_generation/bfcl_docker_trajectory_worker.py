#!/usr/bin/env python3

import json
import sys

from bfcl_eval.utils import (
    populate_test_cases_with_predefined_functions,
)

from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import (
    execute_multi_turn_func_call,
)


def emit(obj):
    sys.stdout.write(
        json.dumps(
            obj,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    )
    sys.stdout.flush()


def main():
    row = None
    namespace = None
    initialized = False

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()

        if not raw_line:
            continue

        request = json.loads(raw_line)

        command = request.get("command")

        if command == "init":
            if initialized:
                raise RuntimeError(
                    "Worker already initialized"
                )

            row = request["row"]
            namespace = request["namespace"]

            entry = {
                "id": row["instance_id"],
                "question": row["question_turns"],
                "initial_config": row["initial_config"],
                "involved_classes": row["involved_classes"],
            }

            processed = (
                populate_test_cases_with_predefined_functions(
                    [entry]
                )[0]
            )

            execute_multi_turn_func_call(
                [],
                row["initial_config"],
                row["involved_classes"],
                namespace,
                row["instance_id"],
                long_context=(
                    "long_context"
                    in row["category"]
                ),
                is_evaL_run=False,
            )

            initialized = True

            emit(
                {
                    "status": "PASS",
                    "command": "init",
                    "instance_id":
                        row["instance_id"],
                    "question":
                        processed["question"],
                    "functions":
                        processed["function"],
                }
            )

        elif command == "execute":
            if not initialized:
                raise RuntimeError(
                    "Worker not initialized"
                )

            calls = request["calls"]

            execution_results, _ = (
                execute_multi_turn_func_call(
                    calls,
                    row["initial_config"],
                    row["involved_classes"],
                    namespace,
                    row["instance_id"],
                    long_context=(
                        "long_context"
                        in row["category"]
                    ),
                    is_evaL_run=False,
                )
            )

            emit(
                {
                    "status": "PASS",
                    "command": "execute",
                    "execution_results":
                        execution_results,
                }
            )

        elif command == "close":
            emit(
                {
                    "status": "PASS",
                    "command": "close",
                }
            )
            return

        else:
            raise RuntimeError(
                f"Unknown worker command: {command}"
            )


if __name__ == "__main__":
    main()
