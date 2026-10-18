"""Supplement completed input ledger with exact footnote evidence, no fits."""
from common import *
import shutil
import pandas as pd
from inputs import STABLE, QUARTERS
record('footnote_evidence')
raw = pd.read_csv(safe(SRC / 'raw/enrollment/cms_monthly_enrollment_2019_2025.csv'), dtype=str, keep_default_na=False)
raw = raw[(raw.preliminary_or_updated == 'U') & (raw.final_report == 'Y')]
lookup = dict(zip(zip(raw.state_abbreviation, raw.reporting_period), raw.total_medicaid_enrollment__footnotes))
p = WORK / 'monthly_population_ledger.csv'
dest = target(WORK / 'monthly_population_ledger_before_footnote_append.csv')
assert not dest.exists()
shutil.copyfile(safe(p), dest)
f = pd.read_csv(safe(p), dtype=str, keep_default_na=False)
f['raw_footnote'] = [lookup[r.state, r.month] for r in f.itertuples()]
f['inside_primary_window_stable'] = f.state.isin(STABLE) & f.calendar_quarter.isin(QUARTERS)
f.to_csv(target(p), index=False)
non = f[f.raw_footnote != ''].copy()
d = non.groupby(['raw_footnote', 'footnote_class']).agg(source_months=('state', 'size'), primary_stable_months=('inside_primary_window_stable', 'sum')).reset_index()
d['Protocol_disposition'] = d.footnote_class.map({'UNAVAILABLE_SYSTEM': 'R1_SET_NA >=2_VALID_MONTHS', 'PARTIAL_POPULATION': 'SEPARATE_PAIRED_QUARTER_EXCLUSION_SENSITIVITY', 'LIMITED_BENEFIT_SCOPE': 'RETAIN; NO_VERIFIED_SAME_DEFINITION_REVISION; OPEN', 'ANYTIME_TIME_SCOPE': 'RETAIN; NO_UNSUPPORTED_RESCALE; OPEN', 'RETROACTIVE_RETAINED': 'RETAIN_NOT_AUTOMATIC_ERROR', 'NONE_OR_OTHER_DOCUMENTED': 'OTHER_SCOPE_UNRESOLVED_RETAIN; NOT_OFFICIAL_CORRECTION'})
cw(OUT / '04B_Monthly_Footnote_Class_Audit.csv', d.to_dict('records'))
jw(WORK / 'footnote_evidence_gate.json', {'Status': 'COMPLETE_VERIFIED', 'unknown_primary_nonempty_months': int(((non.footnote_class == 'NONE_OR_OTHER_DOCUMENTED') & non.inside_primary_window_stable).sum()), 'matrix_not_changed': True, 'monthly_ledger_sha': sha(p), 'footnote_revisions': 'NOT_VERIFIABLE; no new exclusion beyond locked rules'})
print('footnote raw text/classification appended; no data values or fits changed')
