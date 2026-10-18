"""Independent PPML diagnostics, native GLM, and explicit cluster sandwich.
No research files are read, no fitting is done on import.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import warnings
import numpy as np
from scipy import linalg, optimize, stats
import statsmodels.api as sm

def validate(y,X,offset):
    assert np.isfinite(y).all() and (y>=0).all()
    assert np.isfinite(X).all() and np.isfinite(offset).all()
    assert len(y)==len(X)==len(offset)

def rank_info(X):
    c=np.maximum(1,np.max(np.abs(X),axis=0));A=X/c
    singular=linalg.svdvals(A);tau=max(A.shape)*np.finfo(float).eps*singular[0]
    rank=int((singular>tau).sum())
    return {'n':len(X),'k':X.shape[1],'rank':rank,'threshold':float(tau),
       'rank_tau_0_1':int((singular>tau*.1).sum()),'rank_tau_10':int((singular>tau*10).sum()),
       'condition_identified':float(singular[0]/singular[rank-1]) if rank else None,
       'scale':c,'spectrum':singular}

def target_estimable(X,j):
    return rank_info(X)['rank']==rank_info(np.delete(X,j,axis=1))['rank']+1

def separation(X,y):
    c=np.maximum(1,np.max(np.abs(X),axis=0));A=X/c;pos=y>0;zero=y==0
    if not zero.any():return {'detected':False,'status':'NO_ZERO_OUTCOMES','affected':np.zeros(len(y),bool)}
    # d is FREE. The last inequality normalizes sum(A_zero d)<=-1.
    Az=A[zero]
    res=optimize.linprog(np.zeros(A.shape[1]),A_ub=np.vstack([Az,Az.sum(axis=0)]),
      b_ub=np.r_[np.zeros(len(Az)),-1.],A_eq=A[pos],b_eq=np.zeros(pos.sum()),
      bounds=[(None,None)]*A.shape[1],method='highs',
      options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
    if res.status==2:return {'detected':False,'status':'LP_INFEASIBLE','affected':np.zeros(len(y),bool),'message':res.message}
    if not res.success:raise RuntimeError('LP not reliable: '+res.message)
    margins=A@res.x
    eq=float(np.max(np.abs(margins[pos]))) if pos.any() else 0.
    ub=float(np.max(margins[zero]));normal=float(margins[zero].sum())
    assert eq<=1e-8 and ub<=1e-8 and normal<=-1+1e-8,'LP certificate residual failure'
    affected=zero & (margins < -1e-8)
    assert affected.any()
    return {'detected':True,'status':'LP_FEASIBLE_CERTIFIED','direction_scaled':res.x,
       'direction_original':res.x/c,'margins':margins,'positive_equality_max_abs':eq,
       'zero_inequality_max':ub,'normalization_sum':normal,'affected':affected,'message':res.message}

def normalized_score(X,y,mu):
    c=np.maximum(1,np.max(np.abs(X),axis=0));A=X/c
    raw=X.T@(y-mu);scaled=np.abs(A.T@(y-mu))/(1+np.abs(A).T@mu)
    return raw,float(np.max(scaled))

def objective_assessment(history):
    """Protocol permits an explained single initial native IRLS overshoot.
    This narrow interpretation is frozen before research access in C2 note.
    Any later or repeated substantive reverse step remains a failure.
    """
    finite=all(np.isfinite(h['deviance']) for h in history)
    reverse=[{'iteration':i,'increase':b['deviance']-a['deviance'],
              'relative_increase':(b['deviance']-a['deviance'])/(1+abs(a['deviance']))}
             for i,(a,b) in enumerate(zip(history[:-1],history[1:]),1)
             if b['deviance']-a['deviance']>1e-10*(1+abs(a['deviance']))]
    monotonic=finite and not reverse
    initial=finite and len(reverse)==1 and reverse[0]['iteration']==1
    return {'monotonic_objective':monotonic,'reverse_steps':reverse,
            'objective_gate':bool(monotonic or initial),
            'objective_explanation':'MONOTONIC_WITHIN_LOCKED_TOLERANCE' if monotonic else
               ('EXPLAINED_SINGLE_INITIAL_OVERSHOOT' if initial else 'UNEXPLAINED_REVERSE_STEPS')}

def glm_fit(y,X,offset,start,tol):
    validate(y,X,offset)
    assert rank_info(X)['rank']==X.shape[1], 'Unidentified design; no pinv fit'
    model=sm.GLM(y,X,family=sm.families.Poisson(link=sm.families.links.Log()),offset=offset)
    history=[];segments=[];total=0;warnings_all=[];params=start
    # Locked deviance last-five requirement can require a verification continuation.
    # At most five extra native IRLS fits, SAME model/tolerance; genuine iteration
    # histories are concatenated, not padded. Total iterations are strictly <1000.
    for segment in range(6):
        remaining=1000-total
        if remaining<=0:raise RuntimeError('1000 iteration limit')
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            fit=model.fit(start_params=params,maxiter=remaining,tol=tol,atol=tol,rtol=0,
                          method='IRLS',wls_method='qr')
        warnings_all += [type(x.message).__name__+': '+str(x.message) for x in w]
        count=int(fit.fit_history['iteration']);total+=count
        # Entries are [inf, initial deviance, then actual updated iterates].
        dev=fit.fit_history['deviance'];pars=fit.fit_history['params']
        initial=float(dev[1])
        if not history:history.append({'iteration':0,'segment':segment,'deviance':initial,'params':np.asarray(pars[1])})
        for d,b in zip(dev[2:],pars[2:]):
            history.append({'iteration':len(history),'segment':segment,'deviance':float(d),'params':np.asarray(b)})
        segments.append({'segment':segment,'iterations':count,'converged':bool(fit.converged),'tolerance':tol})
        if not fit.converged or total>=1000:break
        params=np.asarray(fit.params);mu=np.asarray(fit.mu)
        raw,score=normalized_score(X,y,mu)
        changes=[abs(b['deviance']-a['deviance'])/(1+abs(a['deviance'])) for a,b in zip(history[:-1],history[1:])]
        if len(changes)>=5 and max(changes[-5:])<=1e-10 and score<=1e-8:break
    mu=np.asarray(fit.mu);raw,score=normalized_score(X,y,mu)
    changes=[abs(b['deviance']-a['deviance'])/(1+abs(a['deviance'])) for a,b in zip(history[:-1],history[1:])]
    finite=bool(np.isfinite(params).all() and np.isfinite(mu).all() and (mu>0).all())
    objective=objective_assessment(history)
    gate=bool(fit.converged and total<1000 and finite and score<=1e-8 and len(changes)>=5 and max(changes[-5:])<=1e-10 and objective['objective_gate'])
    return {'params':np.asarray(fit.params),'mu':mu,'raw_score':raw,'normalized_score':score,
       'deviance':float(fit.deviance),'loglike':float(fit.llf),'history':history,'segments':segments,
       'iterations':total,'converged':bool(fit.converged),'last_five_deviance_relative_max':max(changes[-5:]) if len(changes)>=5 else None,
       **objective,'warnings':warnings_all,'solver_gate':gate}

def covariance(X,y,mu,clusters):
    structural=rank_info(X);r=structural['rank'];assert r==X.shape[1]
    c=structural['scale'];A=X/c;Z=A*np.sqrt(mu)[:,None]
    # Locked Z uses the structural column scales once; do not rescale Z again.
    s=linalg.svdvals(Z);tau=max(Z.shape)*np.finfo(float).eps*s[0]
    assert int((s>tau).sum())==r
    Hs=A.T@(mu[:,None]*A)
    Bs=linalg.solve(Hs,np.eye(r),assume_a='pos')
    bread=Bs/c[:,None]/c[None,:]
    H=X.T@(mu[:,None]*X)
    groups=np.unique(clusters);G=len(groups);n=len(y)
    assert G>1 and n>r
    scores=np.stack([X[clusters==g].T@(y[clusters==g]-mu[clusters==g]) for g in groups])
    meat=scores.T@scores;correction=G/(G-1)*(n-1)/(n-r)
    V=correction*(bread@meat@bread)
    norm=linalg.norm(V,2);symmetry=linalg.norm(V-V.T,2)/max(norm,np.finfo(float).eps)
    vsym=(V+V.T)/2;symnorm=linalg.norm(vsym,2)
    eigen=linalg.eigvalsh(vsym)
    gate=bool(np.isfinite(V).all() and symmetry<=1e-10 and eigen[0]>=-1e-10*max(symnorm,np.finfo(float).eps))
    return {'V':V,'bread':bread,'H':H,'meat':meat,'cluster_scores':scores,'groups':groups,
       'CR1':correction,'n':n,'r':r,'G':G,'weighted_spectrum':s,'weighted_threshold':tau,
       'weighted_rank':int((s>tau).sum()),'symmetry_relative':float(symmetry),
       'min_eigenvalue':float(eigen[0]),'PSD_scale':float(symnorm),
       'weighted_condition':float(s[0]/s[r-1]),'covariance_gate':gate}

def inference(beta,variance,G,distribution='t'):
    assert np.isfinite(variance) and variance>0, 'No variance clamp'
    se=float(np.sqrt(variance));stat=beta/se
    critical=float(stats.t.ppf(.975,G-1)) if distribution=='t' else 1.96
    p=float(2*stats.t.sf(abs(stat),G-1)) if distribution=='t' else float(2*stats.norm.sf(abs(stat)))
    low=beta-critical*se;high=beta+critical*se
    return {'beta':float(beta),'SE':se,'IRR':float(np.exp(beta)),'CI_low':float(np.exp(low)),
            'CI_high':float(np.exp(high)),'P':p,'reference':distribution,'df':G-1 if distribution=='t' else None}
