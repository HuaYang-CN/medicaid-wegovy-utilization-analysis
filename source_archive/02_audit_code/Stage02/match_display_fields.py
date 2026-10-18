"""Compare displayed S7/S8 cells with SAVED numeric fields at display precision.
This formats pre-existing rates/indices; does not calculate rates, group means or Gini.
"""
from pathlib import Path
import csv, json
ROOT = Path(__file__).resolve().parents[2]
SRC = Path('external_data')
WORK = ROOT / '03_audit_outputs/Stage02/_working'

def rows(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
blocks = json.loads((ROOT / '03_audit_outputs/Stage01/_working/supplement_blocks.json').read_text(encoding='utf-8'))
reach = {r['state']: r for r in rows(SRC / 'analysis/state_reach_2025Q4.csv')}
ineq = {r['calendar_quarter']: r for r in rows(SRC / 'analysis/inequality_trends.csv')}
checks = []
for b in blocks:
    if b['type'] != 'table':
        continue
    if b['id'] == 7:
        for i, row in enumerate(b['rows'][1:], 2):
            if row[0] not in reach:
                continue
            r = reach[row[0]]
            expected = [r['state'], 'Covered' if r['coverage_2024'] == '1' else 'Not covered', f"{float(r['obesity_pct']):.1f}", f"{float(r['rx_mid']):.1f}", f"{float(r['enrollment']):.0f}", f"{float(r['rate_100k']):.1f}", f"{float(r['need_adjusted_reach']):.2f}"]
            for j in range(2, 7):
                checks.append({'Table': 'S7', 'Row': i, 'Column': j + 1, 'Key': row[0], 'Displayed': row[j], 'Saved_Formatted': expected[j], 'Matches': row[j].replace(',', '') == expected[j], 'Evidence_File': 'analysis/state_reach_2025Q4.csv'})
    if b['id'] == 8:
        for i, row in enumerate(b['rows'][1:], 2):
            r = ineq[row[0]]
            for j, col, fmt in [(1, 'mean_rate', '.1f'), (2, 'gini', '.3f'), (3, 'coefficient_of_variation', '.3f')]:
                expected = format(float(r[col]), fmt)
                checks.append({'Table': 'S8', 'Row': i, 'Column': j + 1, 'Key': row[0], 'Displayed': row[j], 'Saved_Formatted': expected, 'Matches': row[j] == expected, 'Evidence_File': 'analysis/inequality_trends.csv'})
with (WORK / 'S7_S8_saved_display_checks.csv').open('x', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(checks[0]))
    w.writeheader()
    w.writerows(checks)
print({'checks': len(checks), 'mismatches': [r for r in checks if not r['Matches']]})
