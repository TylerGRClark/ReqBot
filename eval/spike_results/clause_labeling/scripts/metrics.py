import json,sys,os,collections
sys.path.insert(0,os.path.expanduser('~/reqbot-work/scratch/clause_label'))
from cl import *
units,rows,reqs=load_all()
TUNE={'afi10-2402','afi90-802','dafman17-1305','dafpam90-803','CJCSI 6510.02G','DODI 5200.44'}
EXAM={'afi17-101','dafman17-1203','DODI 5200.48','afi17-203','afman17-204','DODI 8551.01'}
CL={uid:clauses_of(u) for uid,u in units.items()}
def flagged_texts(uid,arm):
    """arm: 'B0' or dict (uid|idx)->label. returns list of flagged texts"""
    if arm=='B0': return rows.get(uid,[])
    return [c['text'] for c in CL[uid] if arm.get('%s|%d'%(uid,c['idx']),'NOT_REQUIREMENT')!='NOT_REQUIREMENT']
def unreachable(uid):
    return sum(1 for r in reqs[uid] if not any(match(r,c['text']) for c in CL[uid]))
def metrics(arm,docs,tot=None):
    d=collections.defaultdict(lambda:collections.Counter())
    for uid,u in units.items():
        doc=u['document']
        if doc not in docs: continue
        c=d[doc]; ft=flagged_texts(uid,arm); R=reqs[uid]
        c['units']+=1; c['nreq']+=len(R)
        c['unreach']+=unreachable(uid)
        c['unreach_s']+=sum(1 for r in R if not any(norm(r) in norm(x['text']) for x in CL[uid]))
        c['cov']+=sum(1 for r in R if any(match(r,t) for t in ft))
        c['cov_strict']+=sum(1 for r in R if any(strict(r,t) for t in ft))
        c['flag']+=len(ft)
        c['flag_ok']+=sum(1 for t in ft if any(match(r,t) for r in R))
        if R:
            c['unit_req']+=1
            if not ft: c['skip']+=1
    out={}
    def fin(c):
        return dict(n_req=c['nreq'],recall=c['cov']/max(1,c['nreq']),recall_strict=c['cov_strict']/max(1,c['nreq']),
          precision=c['flag_ok']/max(1,c['flag']),skip=c['skip']/max(1,c['unit_req']),flagged=c['flag'],
          workload=100*c['flag']/max(1,c['nreq']),unreach=c['unreach']/max(1,c['nreq']),unreach_s=c['unreach_s']/max(1,c['nreq']))
    for k,c in d.items(): out[k]=fin(c)
    P=sum(d.values(),collections.Counter()); out['POOLED']=fin(P); out['POOLED']['units']=P['units']
    return out
def show(name,m):
    for k,v in m.items():
        print('%-6s %-16s n=%4d rec=%.3f strict=%.3f prec=%.3f skip=%.3f flag=%5d work/100=%6.1f unreach60=%.3f unreach_strict=%.3f'%(name,k,v['n_req'],v['recall'],v['recall_strict'],v['precision'],v['skip'],v['flagged'],v['workload'],v['unreach'],v['unreach_s']))
if __name__=='__main__':
    for nm,docs in (('TUNE',TUNE),('EXAM',EXAM)):
        print('=====',nm); show('B0',metrics('B0',docs))
