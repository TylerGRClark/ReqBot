import sys
sys.path.insert(0,'.')
from common import *
from cl import clauses_of
U=units(); CLS={k:clauses_of(v) for k,v in U.items()}
old=set(json.load(open(os.path.expanduser('~/reqbot-work/scratch/miss_diag/old24_ids.json'))))
base=json.load(open(HERE+'baseline.json'))
bfound=set().union(*[set(p['found']) for p in base]); never20=set(obl)-bfound
def recs_of(tag):
    d=json.load(open(HERE+f'arm_{tag}.json'))['labels']; recs=[]; n=0
    for uid,cl in CLS.items():
        for c in cl:
            l=d.get('%s|%d'%(uid,c['idx']))
            if l is None: raise SystemExit('missing label '+uid)
            if l!='NOT_REQUIREMENT':
                n+=1; recs.append((U[uid]['document'],dict(requirement_id='%s#%d'%(uid,c['idx']),chunk_id=U[uid]['chunk_id'],source_quote=c['text'])))
    return recs,json.load(open(HERE+f'arm_{tag}.json'))
res={}
for arm in ('L8','L35'):
    for s in (1,2):
        tag=f'{arm}_s{s}'
        if not os.path.exists(HERE+f'arm_{tag}.json'): continue
        recs,d=recs_of(tag); sc=score(recs)
        lab=collections.Counter(d['labels'].values())
        perdoc={}
        for doc in DOCS:
            ob=[k for k in obl if index[k]['document']==doc]
            r=[x for x in recs if x[0]==doc]; sd=score(r)
            perdoc[doc]=dict(n_obl=len(ob),rec=sum(1 for k in ob if k in sc['found'])/len(ob),prec=sd['prec'],flagged=len(r))
        res[tag]=dict(rec=sc['rec_any'],prim=sc['rec_primary'],prec=sc['prec'],n=sc['n'],per100=100*sc['n']/len(obl),old24=len(old&sc['found']),
          n20=len(never20&sc['found']),found=sorted(sc['found']),perdoc=perdoc,labels=dict(lab),unparsed=d['tot']['unparsed'],wall=d['tot'].get('wall'),tally=sc['tally'])
        print(tag,{k:(round(v,3) if isinstance(v,float) else v) for k,v in res[tag].items() if k not in('found','perdoc')})
        for doc,v in perdoc.items(): print('   ',doc,{k:round(x,3) for k,x in v.items()})
json.dump(res,open(HERE+'results.json','w'),indent=1)
bm=lambda k:sum(p[k] for p in base)/6
B=dict(rec=bm('rec'),prec=bm('prec'),n=bm('n'))
print('BASE',B)
for arm in ('L8','L35'):
    t=[res[f'{arm}_s{s}'] for s in (1,2) if f'{arm}_s{s}' in res]
    if len(t)<2: continue
    rec=sum(x['rec'] for x in t)/2; prec=sum(x['prec'] for x in t)/2
    noise=abs(t[0]['rec']-t[1]['rec']); gain=rec-B['rec']; pd=prec-B['prec']
    verdict='PASS' if gain>=0.08 and pd>=-0.05 and gain>noise else ('PROMISING' if 0.04<=gain<0.08 and pd>=-0.05 else 'FAIL')
    print(f'{arm}: rec={rec:.4f} gain={gain*100:+.1f}pt noise={noise*100:.1f}pt prec={prec:.4f} dprec={pd*100:+.1f}pt per100={sum(x["per100"] for x in t)/2:.1f} old24={[x["old24"] for x in t]} never20={[x["n20"] for x in t]} -> {verdict}')
