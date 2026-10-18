# Medicaid Wegovy analysis code release candidate

Version 2.0.0-rc1; prepared locally 2026-10-17. This package supports review of the paper's reported analyses and transparent source tracing. It is not yet an external publication or permanent archive.

Run from this directory using an existing environment matching environment.json. No automatic installation or download is performed.

```
python run.py verify
python run.py figures
python run.py tables
```

verify reconstructs C10 counts from the frozen source-status rows, checks requested keys, saved LP certificate/identifiability, reference and 10 fitted values, complete sandwich and t inference from saved objects. It does not refit them. figures re-renders the six saved-value figures with portable fonts; tables writes the complete frozen result tables to output/tables. Graphing additionally needs reportlab; its tested version is recorded in the release test report.

For a future explicitly requested refit, `python run.py fit-c10` runs only 0/10 using the same numerical core and frozen design. It never refits 5.5, downloads data, or executes other historical entry points. This portable wrapper is statically checked; its fit mode was not invoked in R2 because the authorized original R2 run already succeeded. Do not interpret a locally checked wrapper as another independent refit.

Inputs/data are state aggregates or public NDC source rows; no patient-level records. Missing sources stay unknown, and suppressed assignments are operational scenarios. Data dictionaries are under data/. Source and input provenance CSVs and model_and_figure_manifest.csv provide exact identities and hashes. Read source_provenance.md and INDEPENDENT_QA.md for limitations. No large raw CMS file, patient data, unrelated project, credentials, cached environments or third-party full text is included.

The source archive is complete for the recovered relevant computational modules; it is not a turnkey rerun of every historical audit report. Historical fits were deliberately not repeated. See the detailed result manifest rather than assuming that the presence of a script proves complete reproducibility. Scientific causal NO_GO remains unchanged.
