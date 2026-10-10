#!/usr/bin/env python3
"""Generic, self-inclusive privacy and release-hygiene audit.

Contains no project-specific identity denylist. A separate PRIVATE review is
still needed for contextual re-identification risks. The checker inspects its
own bytes and every regular file in the release tree, not just source code.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = Path(__file__).resolve()

# Patterns intentionally describe generic classes rather than known people,
# hostnames, institutions, or original research accounts.
PATTERNS = {
    'absolute_user_home': re.compile(r'/(?:home|Users)/[^/\s"\x27<>]+', re.I),
    'windows_user_home': re.compile(r'[a-z]:\\\\Users\\\\[^\\\\\s]+', re.I),
    'email_address': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    'orcid_formatted_identifier': re.compile(r'\b\d{4}-\d{4}-\d{4}-[\dX]{4}\b'),
    'common_api_token': re.compile(r'\b(?:sk-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b'),
    'private_key_block': re.compile(r'-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----'),
    'credential_assignment': re.compile(
        r'(?i)\b(?:api[_-]?key|access[_-]?token|secret[_-]?key|password)\b\s*[:=]\s*["\x27][^"\x27\r\n]{12,}["\x27]'
    ),
    'ssh_remote': re.compile(r'\b(?:git' + r'@[^\s]+:[^\s]+|s' + r'sh://[^\s]+)\b', re.I),
    'personal_repo_remote': re.compile(r'https?://[^/\s]+/[^/\s]+/[^/\s]+\.git\b', re.I),
}

bad = []
files = 0
self_checked = False
for path in sorted(ROOT.rglob('*')):
    rel = path.relative_to(ROOT)
    if path.is_symlink():
        bad.append((str(rel), 0, 'symlink_not_allowed'))
        continue
    if '.git' in rel.parts:
        bad.append((str(rel), 0, 'embedded_git_history'))
        continue
    if not path.is_file():
        continue
    # Generated results are unshipped reviewer-local outputs; the released
    # reproduced/.gitkeep is scanned. Archive completeness is independently
    # enforced by the release manifest and clean-ZIP audit.
    if rel.parts[0] == "reproduced" and rel.as_posix() != "reproduced/.gitkeep":
        continue
    files += 1
    if path.resolve() == CHECKER:
        self_checked = True
    # Decode even binary attachments: security checks also cover long printable
    # strings embedded in blobs; source/manifest hashes are checked separately.
    content = path.read_bytes().decode('utf-8', 'ignore')
    for label,regex in PATTERNS.items():
        matches = list(regex.finditer(content))
        for match in matches[:8]:
            line = content.count('\n',0,match.start()) + 1
            bad.append((str(rel),line,label))
    # Filename check is structural/generic, not an identity-specific denylist.
    if re.search(r'(?i)(?:^|/)(?:\.env(?:\.[^/]+)?|id_rsa|id_ed25519|credentials\.(?:json|yaml|yml)|authorized_keys)$',str(rel)):
        bad.append((str(rel),0,'sensitive_filename'))

print(f'RELEASE_FILES_SCANNED={files}')
print('PASS anonymity_checker_self_included' if self_checked else 'FAIL anonymity_checker_self_missing')
if bad:
    for rel,line,label in bad[:40]:
        # Do not print secret values in audit logs.
        print(f'FAIL {label} {rel}:{line}')
else:
    print('PASS generic_content_filename_and_symlink_scan')
if not self_checked:
    bad.append(('scripts/check_anonymity.py',0,'self_not_scanned'))
print('FINAL_ANONYMITY_STATUS=' + ('FAIL' if bad else 'PASS'))
raise SystemExit(1 if bad else 0)
