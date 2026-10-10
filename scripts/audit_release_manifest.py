#!/usr/bin/env python3
"""Verify release-manifest size/digest/completeness; generated outputs are excluded."""
import csv
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = root/'RELEASE_MANIFEST.tsv'
with manifest.open(newline='',encoding='utf-8') as f:
    entries=list(csv.DictReader(f, delimiter='\t'))

def packaged(p):
    rel=p.relative_to(root)
    if rel.as_posix()=='RELEASE_MANIFEST.tsv':return False
    if rel.parts[0]=='reproduced' and rel.as_posix()!='reproduced/.gitkeep': return False
    if '__pycache__' in rel.parts or rel.suffix in ('.pyc','.pyo'):return False
    return True

actual={p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file() and packaged(p)}
indexed={e['path']:e for e in entries}
errors=[]
if len(entries)!=len(indexed):errors.append('duplicate_manifest_paths')
for rel,e in indexed.items():
    if rel not in actual:
        errors.append('missing_file:'+rel);continue
    p=actual[rel]
    if len(p.read_bytes()) != int(e['bytes']): errors.append('size:'+rel)
    if hashlib.sha256(p.read_bytes()).hexdigest() != e['sha256']: errors.append('digest:'+rel)
for rel in sorted(set(actual)-set(indexed)): errors.append('unindexed_file:'+rel)
print('MANIFEST_FILE_COUNT='+str(len(indexed)))
print('MANIFEST_CHECK_ERRORS='+str(len(errors)))
for line in errors[:25]:print('FAIL '+line)
print('FINAL_RELEASE_MANIFEST_STATUS='+('PASS' if not errors else 'FAIL'))
raise SystemExit(1 if errors else 0)
