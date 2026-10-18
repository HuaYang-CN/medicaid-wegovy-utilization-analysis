"""Portable release entry. No downloads; fitting only via explicit fit-c10."""
from pathlib import Path
import os,sys,csv,json,hashlib,shutil,ast
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'portable'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def verify():
    import numpy as np
    import pandas as pd
    import c10,stat_core as sc,independent_core as ic
    result={'scope':'Frozen count reconstruction, design, certificates and saved-object numerical checks; NO REFITS','checks':{}}
    R=result['checks'];ndc=table(ROOT/'data/CleanF0_NDC_source_components.csv')
    used=[r for r in ndc if r['included_in_clean_F0']=='True'];groups={}
    for r in used:groups.setdefault((r['state'],r['calendar_quarter'],r['analytic_brand']),[]).append(r)
    ref=pd.read_csv(ROOT/'data/C10_SUPP_5P5_REFERENCE_requested.csv',float_precision='round_trip')
    expected={r['scenario']:r for r in table(ROOT/'expected_results.csv')}
    for ident,val in [('C10_SUPP_0',0),('C10_SUPP_5P5_REFERENCE',5.5),('C10_SUPP_10',10)]:
        f=pd.read_csv(ROOT/'data'/(ident+'_requested.csv'),float_precision='round_trip')
        assert c10.keys(f)==c10.keys(ref) and len(f)==348 and f.state.nunique()==29
        assert '2024Q1' not in set(f.calendar_quarter)
        computed=[sum(val if r['suppressed']=='True' else float(r['observed']) for r in groups[(x.state,x.calendar_quarter,x.analytic_brand)]) for x in f.itertuples()]
        assert np.array_equal(f.y.to_numpy(),computed)
        assert np.array_equal(f.observed_rx_sum.to_numpy(),ref.observed_rx_sum.to_numpy())
        assert np.array_equal(f.offset.to_numpy(),ref.offset.to_numpy())
        X,names=c10.design(f);assert X.shape==(348,70)
        if val==0:
            cert=json.loads((ROOT/'saved/c10/C10_SUPP_0/separation_round_0.json').read_text())['certificate']
            margin=X@np.asarray(cert['direction_original']);p=f.y.to_numpy()>0;z=~p
            assert max(abs(margin[p]))<=1e-9 and max(margin[z])<=1e-9 and margin[z].sum()<=-1+1e-8
            drop=np.asarray(cert['affected'],dtype=bool)
            assert [c10.keys(f)[i] for i in np.flatnonzero(drop)]==['NM|2023Q3|WEGOVY','NM|2023Q4|WEGOVY']
            xe,ns=c10.design(f.loc[~drop]);j=ns.index('Post×DDD')
            assert sc.rank_info(xe)['rank']==69 and not sc.target_estimable(xe,j)
            assert all(expected[ident][k]=='NA' for k in ['IRR','SE','P','CI_low','CI_high'])
            R[ident]={'source_counts':'PASS','certificate_margins':'PASS','rank':69,'target':'NOT_IDENTIFIABLE','new_fit':False}
        else:
            path=ROOT/('saved/reference/primary_run_1_full.npz' if val==5.5 else 'saved/c10/C10_SUPP_10/native_1.npz')
            o=np.load(path,allow_pickle=False);beta=o['params'];mu=o['mu'];V=o['V']
            assert np.allclose(np.exp(f.offset.to_numpy()+X@beta),mu,rtol=1e-9,atol=1e-8)
            cv=ic.sandwich(X,f.y.to_numpy(),mu,f.state.to_numpy())
            assert ic.close(cv['V'],V,1e-8,1e-4)
            j=names.index('Post×DDD');est=ic.infer(beta[j],cv['V'][j,j],cv['G'])
            for k in ['beta','SE','IRR','CI_low','CI_high','P']:assert abs(est[k]-float(expected[ident][k]))<1e-6*(1+abs(float(expected[ident][k]))),k
            _,score=sc.normalized_score(X,f.y.to_numpy(),mu);assert score<=1e-8
            R[ident]={'source_counts':'PASS','rank':sc.rank_info(X)['rank'],'full_covariance':'PASS','inference':'PASS','score':score,'new_fit':False}
    for p in (ROOT/'source_archive').rglob('*.py'):ast.parse(p.read_text('utf-8'))
    R['source_archive_syntax']='PASS'
    for r in table(ROOT/'model_and_figure_manifest.csv'):
        for fld,h in [('script','script_sha256'),('input','input_sha256'),('result_csv','result_csv_sha256')]:assert sha(ROOT/r[fld])==r[h],(r['display'],fld)
    R['manifest_links']='PASS'
    for r in table(ROOT/'source_code_provenance.csv'):assert sha(ROOT/r['release_path'])==r['release_sha256']
    R['source_hashes']='PASS'
    result['status']='PASS_SUPPORTED_CHECKS_ONLY'
    import platform,importlib.metadata as im
    result['environment']={'python':platform.python_version(),'numpy':im.version('numpy'),'scipy':im.version('scipy'),'pandas':im.version('pandas'),'statsmodels':im.version('statsmodels')}
    out=ROOT/'output';out.mkdir(exist_ok=True);(out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
def tables():
    dest=ROOT/'output/tables';dest.mkdir(parents=True,exist_ok=True)
    for p in (ROOT/'data').glob('Table_*.csv'):shutil.copyfile(p,dest/p.name)
    print('Copied frozen tables with exact values; no model execution.')
def fit_c10():
    import c10
    c10.WORK.mkdir(parents=True,exist_ok=True)
    for ident in ['C10_SUPP_0','C10_SUPP_10']:
        shutil.copyfile(ROOT/'data'/(ident+'_requested.csv'),c10.WORK/(ident+'_requested.csv'))
        print(json.dumps(c10.scenario(ident),default=str))
    print('Reference 5.5 deliberately not fitted. Compare against expected_results.csv.')
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['verify','figures','tables','fit-c10']);a=p.parse_args()
    if a.action=='verify':verify()
    elif a.action=='figures':
        import figures;figures.main();print('Rendered six figures from frozen results; portable standard font.')
    elif a.action=='tables':tables()
    else:fit_c10()
