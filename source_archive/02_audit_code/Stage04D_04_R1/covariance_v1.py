"""Accepted stable covariance factor algorithm; no input/fit/writes on import."""
import numpy as np
from scipy import linalg as la

def native_factor(X, y, mu, cl):
    c = np.maximum(1, np.max(np.abs(X), axis=0))
    A = X / c
    Z = A * np.sqrt(mu)[:, None]
    s = la.svdvals(Z)
    tau = max(X.shape) * np.finfo(float).eps * s[0]
    r = X.shape[1]
    assert int((s > tau).sum()) == r
    Hs = A.T @ (mu[:, None] * A)
    chol = la.cho_factor(Hs, lower=True)
    Bs = la.cho_solve(chol, np.eye(r))
    bread = Bs / c[:, None] / c[None, :]
    H = X.T @ (mu[:, None] * X)
    groups = np.unique(cl)
    G = len(groups)
    n = len(y)
    scores = np.stack([X[cl == g].T @ (y[cl == g] - mu[cl == g]) for g in groups])
    meat = scores.T @ scores
    influence = la.cho_solve(chol, (scores / c).T) / c[:, None]
    corr = G / (G - 1) * (n - 1) / (n - r)
    V = corr * (influence @ influence.T)
    symmetry = float(la.norm(V - V.T, 2) / max(la.norm(V, 2), np.finfo(float).eps))
    vs = (V + V.T) / 2
    emin = float(la.eigvalsh(vs)[0])
    vnorm = float(la.norm(vs, 2))
    gate = bool(np.isfinite(V).all() and symmetry <= 1e-10 and (emin >= -1e-10 * max(vnorm, np.finfo(float).eps)))
    return {'V': V, 'bread': bread, 'H': H, 'meat': meat, 'cluster_scores': scores, 'groups': groups, 'cluster_influence': influence.T, 'weighted_spectrum': s, 'CR1': corr, 'n': n, 'G': G, 'r': r, 'weighted_rank': int((s > tau).sum()), 'weighted_condition': float(s[0] / s[r - 1]), 'symmetry_relative': symmetry, 'min_eigenvalue': emin, 'PSD_scale': vnorm, 'covariance_gate': gate}
