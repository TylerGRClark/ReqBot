"""gold2 EXAM harness (PREREG4 / AMEND1). Loads ONLY the 5 gold2 EXAM documents; every other document is refused."""
import json,re,os,sys,hashlib,time,random,collections
W=os.path.expanduser('~/reqbot-work/scratch/gold2_exam/'); G=os.path.expanduser('~/reqbot-work/scratch/gold2/'); C=os.path.expanduser('~/reqbot-work/scratch/gold2_cnssi/')
sys.path.insert(0,W)
from cl import split_clauses,match,strict,norm,load,LABELS
EXAM4={'dafman17-1301','afi13-550','DODI 5200.01','NIST.SP.800-125'}
ALLOWED=EXAM4|{'CNSSI_No1253'}
def guard(doc):
    if doc not in ALLOWED: raise SystemExit('REFUSED: %r is not a gold2 EXAM document'%doc)
units={}; reqs={}; rows=collections.defaultdict(list)
for uf,gf,rf in ((G+'units_gold2.jsonl',G+'gold_both.json',G+'rows_gold2.jsonl'),(C+'units_gold2_cnssi.jsonl',C+'gold_both_cnssi.json',C+'rows_gold2_cnssi.jsonl')):
    gb=json.load(open(gf))
    for u in load(uf):
        if u['document'] in ALLOWED and u.get('split')=='exam':   # others dropped at load, never touched
            units[u['unit_id']]=u; reqs[u['unit_id']]=gb.get(u['unit_id'],[])
    for r in load(rf):
        if r['unit_id'] in units: rows[r['unit_id']].append(r['quote'])
    del gb
for u in units.values(): guard(u['document'])
def clauses_of(u):
    guard(u['document'])
    t=u['text']; cl=[]
    for i,(s,e) in enumerate(split_clauses(t)):
        cl.append(dict(unit_id=u['unit_id'],idx=i,text=t[s:e],lead=t[s:e].rstrip().endswith(':'),document=u['document']))
    last=None
    for c in cl:
        c['ctx_lead']=last if not c['lead'] else None
        if c['lead']: last=c['text']
        c['heading']=u.get('heading') or ''; c['ref']=u.get('ref') or ''
    return cl
CL={uid:clauses_of(u) for uid,u in units.items()}
ALLC=[c for uid in units for c in CL[uid]]
def clause_block(items):
    parts=[]
    for i,c in enumerate(items,1):
        guard(c['document'])
        ctx=[]
        if c['heading']: ctx.append('Heading: '+c['heading'][:150])
        if c['ref']: ctx.append('Paragraph: '+c['ref'][:60])
        if c['ctx_lead']: ctx.append('Lead-in line above: '+c['ctx_lead'][:300])
        txt=re.sub(r'[ \t]{2,}',' ',c['text'])[:1200]
        parts.append('[%d]\nContext: %s\nClause: %s'%(i,' | '.join(ctx) if ctx else '(none)',txt))
    return '\n\n'.join(parts)
CACHE=W+'cache.jsonl'; _cache=None
def cache_get(k):
    global _cache
    if _cache is None:
        _cache={}
        if os.path.exists(CACHE):
            for l in open(CACHE):
                try: r=json.loads(l); _cache[r['k']]=r
                except Exception: pass
    return _cache.get(k)
def cache_put(k,rec):
    rec['k']=k; _cache[k]=rec
    with open(CACHE,'a') as f: f.write(json.dumps(rec)+'\n')
_url=None
def ollama_url():
    global _url
    if _url is None:
        sys.path.insert(0,'/home/coder/grc-ai-system')
        from core import config; _url=config.load().ollama_url
    return _url
def ollama(model,prompt,npred=300,timeout=900):
    import requests
    body={"model":model,"stream":False,"messages":[{"role":"user","content":prompt}],"options":{"temperature":0,"num_ctx":8192,"num_predict":npred}}
    if model.startswith('ornith'): body['think']=False
    r=requests.post(ollama_url().rstrip('/')+'/api/chat',json=body,timeout=timeout); r.raise_for_status()
    return r.json()['message']['content']
def parse(ans,n,labels=LABELS):
    m=re.search(r'\[.*\]',ans,re.S)
    if not m: return None
    try: arr=json.loads(m.group(0))
    except Exception: return None
    got={}
    for o in arr:
        if not isinstance(o,dict): return None
        try: i=int(str(o.get('id')).strip('[] '))
        except Exception: return None
        l=str(o.get('label','')).strip().upper().replace(' ','_')
        if l not in labels: return None
        got[i]=l
    if set(got)!=set(range(1,n+1)): return None
    return [got[i] for i in range(1,n+1)]
STATS=collections.Counter()
def call_cached(model,prompt,n,npred):
    k=hashlib.sha256((model+'\n'+prompt).encode()).hexdigest()
    r=cache_get(k)
    if r: STATS['cached']+=1; return r['labels'],r.get('unparsed',0),r.get('secs',0)
    secs=0; labs=None; ans=''
    for attempt in range(2):
        t=time.time()
        try: ans=ollama(model,prompt,npred)
        except Exception as e: ans=''; print('ollama error',e,file=sys.stderr,flush=True); time.sleep(5)
        secs+=time.time()-t; STATS['called']+=1
        labs=parse(ans,n)
        if labs: break
    unp=0
    if not labs: labs=['UNSURE']*n; unp=1
    cache_put(k,dict(model=model,labels=labs,unparsed=unp,secs=secs,ans=ans[:1500]))
    return labs,unp,secs
def label_items(model,items,cfg):
    for c in items: guard(c['document'])
    p=open(W+cfg['prompt']).read().replace('{CLAUSES}',clause_block(items))
    return call_cached(model,p,len(items),300)
def run_arm(model,cfg,seed,out):
    bs=cfg.get('bs',4); order=list(ALLC); random.Random(seed).shuffle(order)
    res={}; tot=dict(secs=0.0,unparsed=0,batches=0); t0=time.time()
    for i in range(0,len(order),bs):
        items=order[i:i+bs]
        labs,unp,secs=label_items(model,items,cfg)
        for c,l in zip(items,labs): res['%s|%d'%(c['unit_id'],c['idx'])]=l
        tot['secs']+=secs; tot['unparsed']+=unp; tot['batches']+=1
        if tot['batches']%25==0: print(model,seed,tot['batches'],'/',-(-len(order)//bs),'%.0fs'%(time.time()-t0),dict(STATS),flush=True)
    tot['wall']=time.time()-t0
    json.dump(dict(labels=res,tot=tot,cfg=cfg,model=model,seed=seed),open(out,'w'))
    return res,tot
def flagged_texts(uid,arm):
    if arm=='B0': return rows.get(uid,[])
    return [c['text'] for c in CL[uid] if arm.get('%s|%d'%(uid,c['idx']),'NOT_REQUIREMENT')!='NOT_REQUIREMENT']
def unreachable(uid):
    return sum(1 for r in reqs[uid] if not any(match(r,c['text']) for c in CL[uid]))
def _acc(arm,select):
    c=collections.Counter()
    for uid,u in units.items():
        if not select(u): continue
        ft=flagged_texts(uid,arm); R=reqs[uid]
        c['units']+=1; c['nreq']+=len(R)
        c['cov']+=sum(1 for r in R if any(match(r,t) for t in ft))
        c['cov_s']+=sum(1 for r in R if any(strict(r,t) for t in ft))
        c['flag']+=len(ft); c['flag_ok']+=sum(1 for t in ft if any(match(r,t) for r in R))
        c['unreach']+=unreachable(uid)
        c['unreach_s']+=sum(1 for r in R if not any(norm(r) in norm(x['text']) for x in CL[uid]))
        if R:
            c['unit_req']+=1
            if not ft: c['skip']+=1
    return c
def fin(c):
    n=max(1,c['nreq'])
    return dict(n=c['nreq'],units=c['units'],recall=c['cov']/n,recall_s=c['cov_s']/n,precision=c['flag_ok']/max(1,c['flag']),skip=c['skip']/max(1,c['unit_req']),
                flagged=c['flag'],work=100*c['flag']/n,unreach=c['unreach']/n,unreach_s=c['unreach_s']/n)
def metrics(arm):
    out={}
    for d in sorted(ALLOWED): out[d]=fin(_acc(arm,lambda u,d=d:u['document']==d))
    out['POOLED_noCNSSI']=fin(_acc(arm,lambda u:u['document'] in EXAM4))
    out['POOLED_all5']=fin(_acc(arm,lambda u:True))
    out['TABLE_units']=fin(_acc(arm,lambda u:u.get('has_table')))
    out['NONTABLE_units']=fin(_acc(arm,lambda u:not u.get('has_table')))
    return out
def show(name,m):
    for k,v in m.items():
        print('%-10s %-16s u=%3d n=%3d rec=%.3f strict=%.3f prec=%.3f skip=%.3f flag=%4d work=%5.1f unr60=%.3f unrS=%.3f'%(name,k,v['units'],v['n'],v['recall'],v['recall_s'],v['precision'],v['skip'],v['flagged'],v['work'],v['unreach'],v['unreach_s']))
