"""Readonly targeted evidence for three C3 unmapped records, no aggregate/fit."""
from common import *
from collections import defaultdict
a = jr(WORK / 'source_ledger_A.json')['anomalies']
by = defaultdict(set)
for r in a:
    by[r['file']].add(r['row'])
fields = ['state', 'year', 'quarter', 'ndc', 'utilization_type', 'analytic_brand', 'product_name', 'suppression_used', 'number_of_prescriptions']
out = []
for rel, ids in by.items():
    with safe(SRC / rel).open(encoding='utf-8-sig', newline='') as f:
        for ix, r in enumerate(csv.DictReader(f), 1):
            if ix in ids:
                out.append({'file': rel, 'row': ix, **{k: r[k] for k in fields}})
            if ix >= max(ids):
                break
jw(WORK / 'C3_anomaly_targeted_evidence.json', out)
print(out)
