#!/usr/bin/env python3
"""Read-only Manuscript coverage audit. Never claims missing extensions reproduced."""
import csv
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((root/'docs/PAPER_COVERAGE_MATRIX.tsv').open(encoding='utf-8',newline=''),delimiter='\t'))
allowed={'CORE_REPLAY','SOURCE_INSPECTION','NOT_INCLUDED'}
errors=[]
for i,row in enumerate(rows,1):
    cls=row['coverage_class']
    if cls not in allowed:errors.append(f'{i}:unknown_class:{cls}')
    if cls=='NOT_INCLUDED' and (row['implementation'] or row['frozen_authority'] or row['verification_command']):
        errors.append(f'{i}:unsubstantiated_extension_replay')
    if cls!='NOT_INCLUDED':
        for field in ['implementation','frozen_authority']:
            if not row[field]:errors.append(f'{i}:missing_{field}')
            for rel in row[field].split(';'):
                if rel and (rel.startswith('/') or '..' in Path(rel).parts or not (root/rel).is_file()):
                    errors.append(f'{i}:missing_or_unsafe_path:{rel}')
    if not row['scientific_boundary']:errors.append(f'{i}:no_scientific_boundary')
counts=Counter(x['coverage_class'] for x in rows)
print('CURRENT=PAPER_COVERAGE_AUDIT')
print('MAPPED_ITEMS='+str(len(rows)))
for k in sorted(allowed):print(k+'='+str(counts[k]))
for e in errors:print('FAIL='+e)
print('COVERAGE_INVENTORY_STATUS='+('PASS' if not errors else 'FAIL'))
print('FULL_EXTENSION_REPRODUCTION_STATUS=OPEN' if counts['NOT_INCLUDED'] else 'FULL_EXTENSION_REPRODUCTION_STATUS=NOT_ASSESSED')
raise SystemExit(1 if errors else 0)
