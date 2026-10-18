"""R2 adapter of inspected Stage04C_R2_R2 independent numerical functions.
Function mathematics unchanged; only local history writer dependency replaced.
No imports of historical entry points and no I/O/fitting on import.
"""
import math,json
import numpy as np
from scipy import stats
def save_history(path, obj):
    path.write_text(json.dumps(obj,default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x)),encoding='utf-8')
def close(v,w,ab,rel):return bool(np.all(np.abs(v-w)<=ab+rel*np.abs(w)))

def newton(y,X,off,d):
    b=np.zeros(X.shape[1]);b[0]=math.log(float(y.sum()/np.exp(off).sum()));hist=[]
    def calc(b):
        z=X@b
        with np.errstate(over='ignore',invalid='ignore'):mu=np.exp(off+z)
        if not np.isfinite(mu).all() or (mu<=0).any():return None
        obj=float(np.sum(mu-y*z));g=np.einsum('ij,i->j',X,mu-y);H=np.einsum('ij,i,ik->jk',X,mu,X)
        score=float(np.max(np.abs(g)/(1+np.einsum('ij,i->j',np.abs(X),mu))))
        D=float(2*np.sum(np.where(y>0,y*np.log(np.where(y>0,y,1)/mu),0)-(y-mu)))
        return obj,mu,g,H,score,D
    for i in range(1000):
        v=calc(b);assert v is not None,'Nonfinite independent Newton iterate';obj,mu,g,H,score,D=v
        hist.append({'iteration':i,'objective':obj,'deviance':D,'score':score,'params':b.copy()});save_history(d/'independent_Newton_history.json',hist)
        changes=[abs(v['deviance']-u['deviance'])/(1+abs(u['deviance'])) for u,v in zip(hist[:-1],hist[1:])]
        if score<=1e-10 and len(changes)>=5 and max(changes[-5:])<=1e-10:return b,mu,hist
        direction=np.linalg.solve(H,-g);slope=float(g@direction);assert slope<=0
        step=1.;accepted=False
        for ls in range(60):
            bv=b+step*direction;vv=calc(bv);z=step*(X@direction)
            with np.errstate(over='ignore',invalid='ignore'):delta=float(np.sum(mu*np.expm1(z)-y*z))
            if vv is not None and math.isfinite(delta) and delta<=1e-4*step*slope:accepted=True;break
            step*=.5
        assert accepted,'Independent Armijo60 trial failure';hist[-1]['step']=step;hist[-1]['line_search_trials']=ls+1;b=bv
    raise RuntimeError('Independent Newton1000 iteration limit')

def sandwich(X,y,mu,cl):
    n,k=X.shape;H=np.einsum('ij,i,ik->jk',X,mu,X);bread=np.linalg.solve(H,np.eye(k));gs,inv=np.unique(cl,return_inverse=True);scores=np.zeros((len(gs),k));np.add.at(scores,inv,X*(y-mu)[:,None]);meat=np.einsum('gi,gj->ij',scores,scores)
    scale=np.maximum(1,np.max(np.abs(X),axis=0));s=np.linalg.svd(X/scale,compute_uv=False);tau=max(X.shape)*np.finfo(float).eps*s[0];r=int((s>tau).sum());sw=np.linalg.svd((X/scale)*np.sqrt(mu)[:,None],compute_uv=False);tw=max(X.shape)*np.finfo(float).eps*sw[0];assert r==k and int((sw>tw).sum())==r
    G=len(gs);corr=G/(G-1)*(n-1)/(n-r);V=corr*(bread@meat@bread)
    return {'H':H,'bread':bread,'meat':meat,'cluster_scores':scores,'groups':gs,'V':V,'CR1':corr,'n':n,'r':r,'G':G,'score':np.einsum('ij,i->j',X,y-mu),'weighted_rank':int((sw>tw).sum())}

def infer(b,var,G):
    assert math.isfinite(var) and var>0;se=math.sqrt(var);crit=float(stats.t.isf(.025,G-1));p=float(2*stats.t.cdf(-abs(b/se),G-1))
    return {'beta':float(b),'SE':se,'IRR':math.exp(b),'CI_low':math.exp(b-crit*se),'CI_high':math.exp(b+crit*se),'P':p,'df':G-1}
