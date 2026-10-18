"""Diagnose failed C2 artificial solver test; no research file access."""
from common import *
import numpy as np
from stat_core import glm_fit
r = glm_fit(np.array([1.0, 3.0, 2.0, 6.0]), np.ones((4, 1)), np.zeros(4), np.zeros(1), 1e-12)

def clean(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, dict):
        return {k: clean(w) for k, w in v.items()}
    if isinstance(v, list):
        return [clean(w) for w in v]
    return v
jw(WORK / 'C2_solver_micro_diagnostic.json', clean(r))
print(clean(r))
