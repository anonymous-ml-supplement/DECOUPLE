# Anonymization notes

This peer-review snapshot is derived from frozen scientific authorities without changing selections, terminal outcomes, scores, or reported statistics.

Publication-surface normalization removes or neutralizes author/lab usernames, hostnames, institution-specific paths, scheduler allocation labels, local environment names, private Git metadata, and credentials. Neutral placeholders such as `__DECOUPLE_ROOT__`, `__EXTERNAL_PRM_WORKSPACE__`, `__MATH_PRM_ENV__`, `__TOOL_PRM_ENV__`, and `__SCHEDULER_QOS__` denote non-scientific local metadata.

For frozen artifacts whose bytes change because of this release-only normalization, `artifacts/AUTHORITY_HASH_MAP.tsv` records the private-authority SHA-256 and the released-copy SHA-256. Scientific payload fields used by the paper analyses are unchanged.

The public archive intentionally excludes raw provider credentials, private repository metadata, local virtual environments, scheduler logs, and third-party model/data assets that are not necessary for the zero-API paper reproduction.
