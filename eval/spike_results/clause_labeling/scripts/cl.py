import json,re,os,sys,glob,collections,hashlib,time,random
sys.path.insert(0,'/home/coder/grc-ai-system')
S=os.path.expanduser('~/reqbot-work/scratch/silver/')
HERE=os.path.expanduser('~/reqbot-work/scratch/clause_label/')
def norm(s): return re.sub(r'\s+',' ',s).strip().lower()
def toks(s): return re.findall(r'[a-z0-9]+',s.lower())
def load(p): return [json.loads(l) for l in open(p) if l.strip()]
def match(a,b,th=0.6):
    na,nb=norm(a),norm(b)
    if na in nb or nb in na: return True
    ta,tb=toks(a),toks(b)
    if not ta or not tb: return False
    c=collections.Counter(tb); ov=0
    for w in ta:
        if c[w]>0: ov+=1;c[w]-=1
    return ov/min(len(ta),len(tb))>=th
def strict(a,b):
    na,nb=norm(a),norm(b); return na in nb or nb in na

def load_all():
    units={}
    for f in ('units.jsonl','units2.jsonl','units3.jsonl'):
        for u in load(S+f): units[u['unit_id']]=u
    rows=collections.defaultdict(list)
    for f in ('rows.jsonl','rows2.jsonl','rows3.jsonl'):
        for r in load(S+f): rows[r['unit_id']].append(r['quote'])
    def labs(x):
        d={}
        for p in glob.glob(S+'labels*/A_%s_*.jsonl'%x):
            for r in load(p): d[r['unit_id']]=r['obligations']
        return d
    AX,AY=labs('X'),labs('Y')
    reqs={}
    for uid in AX:
        if uid in AY and uid in units:
            reqs[uid]=[r for r in AX[uid] if any(match(r,y,0.8) for y in AY[uid])]
    return units,rows,reqs

# ---- (a) splitter
ABBR=('e.g.','i.e.','u.s.','no.','para.','paras.','fig.','etc.','vs.','dr.','mr.','sec.','art.','cf.','inc.','dept.','gen.','col.','lt.','mil.')
SENT=re.compile(r'(?<=[.!?])["\')\]]*\s+(?!\(T-\d\))(?=["\'(\[]?[A-Z0-9])')
LISTSTART=re.compile(r'^\s*([-*\u2022]\s|\(?[0-9]{1,2}[.)]\s|\(?[a-zA-Z][.)]\s|\([0-9a-zA-Z]{1,3}\)\s|\|)')
ENDS=re.compile(r'[.!?:;]["\')\]]*(\s*\(T-\d\)\.?)?\s*$')
ABBRRE=re.compile(r'^(\(?[A-Za-z]\.){1,}$|^(no|nos|para|paras|fig|etc|vs|dr|mr|sec|art|cf|inc|dept|gen|col|lt|mil|ch|vol|att|atch)\.$',re.I)
def split_clauses(text):
    """list of (start,end); text[start:end] is the clause itself. Lines are joined unless the next line starts a list item/table row, a blank line intervenes, or the previous line ends a sentence."""
    lines=[];pos=0
    for line in text.split('\n'):
        lines.append((pos,line)); pos+=len(line)+1
    blocks=[];cur=None
    for ls,line in lines:
        if not re.search(r'[A-Za-z]{2}',line): cur=None; continue
        st=ls+(len(line)-len(line.lstrip())); en=ls+len(line.rstrip())
        if cur is not None and not LISTSTART.match(line) and not ENDS.search(text[cur[0]:cur[1]]):
            cur[1]=en
        else:
            cur=[st,en]; blocks.append(cur)
    out=[]
    for bs,be in blocks:
        seg=text[bs:be]; a=0
        for m in SENT.finditer(seg):
            pre=seg[a:m.start()+1].split()
            last=pre[-1] if pre else ''
            if ABBRRE.match(last) or re.fullmatch(r'\d+\.\d+\.?|[A-Za-z0-9]{1,2}\.',last): continue
            out.append((bs+a,bs+m.start()+1)); a=m.end()
        out.append((bs+a,be))
    return [(s,e) for s,e in out if e>s and re.search(r'[A-Za-z]{2}',text[s:e])]
def clauses_of(u):
    t=u['text']; cl=[]
    for i,(s,e) in enumerate(split_clauses(t)):
        cl.append(dict(unit_id=u['unit_id'],idx=i,text=t[s:e],lead=t[s:e].rstrip().endswith(':')))
    # (b) context: nearest preceding lead-in
    last=None
    for c in cl:
        c['ctx_lead']=last if not c['lead'] else None
        if c['lead']: last=c['text']
        c['heading']=u.get('heading') or ''; c['ref']=u.get('ref') or ''
    return cl

# ---- (c) labeling
LABELS=('DUTY','PROHIBITION','PERMISSION','NOT_REQUIREMENT','UNSURE')
PROMPT_FILE=HERE+'prompt_current.txt'
def prompt_text(): return open(PROMPT_FILE).read()
def clause_block(items):
    parts=[]
    for i,c in enumerate(items,1):
        ctx=[]
        if c['heading']: ctx.append('Heading: '+c['heading'][:150])
        if c['ref']: ctx.append('Paragraph: '+c['ref'][:60])
        if c['ctx_lead']: ctx.append('Lead-in line above: '+c['ctx_lead'][:300])
        parts.append('[%d]\nContext: %s\nClause: %s'%(i,' | '.join(ctx) if ctx else '(none)',re.sub(r'[ \t]{2,}',' ',c['text'])[:1200]))
    return '\n\n'.join(parts)
CACHE=HERE+'cache.jsonl'
_cache=None
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
        from core import config; _url=config.load().ollama_url
    return _url
def ollama(model,prompt,timeout=600):
    import requests
    body={"model":model,"stream":False,"messages":[{"role":"user","content":prompt}],"options":{"temperature":0,"num_ctx":8192,"num_predict":300}}
    if model.startswith('ornith'): body['think']=False
    r=requests.post(ollama_url().rstrip('/')+'/api/chat',json=body,timeout=timeout); r.raise_for_status()
    return r.json()['message']['content']
def parse(ans,n):
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
        if l not in LABELS: return None
        got[i]=l
    if set(got)!=set(range(1,n+1)): return None
    return [got[i] for i in range(1,n+1)]
STATS=collections.Counter()
def label_batch(model,items):
    prompt=prompt_text().replace('{CLAUSES}',clause_block(items))
    ver=hashlib.sha256(prompt_text().encode()).hexdigest()[:12]
    k=hashlib.sha256((model+'\n'+ver+'\n'+prompt).encode()).hexdigest()
    r=cache_get(k)
    if r: STATS['cached']+=1; return r['labels'],r.get('unparsed',0),r.get('secs',0),r.get('calls',1)
    secs=0;calls=0;labels=None
    for attempt in range(2):
        t=time.time()
        try: ans=ollama(model,prompt)
        except Exception as e: ans=''; print('ollama error',e,file=sys.stderr); time.sleep(5)
        secs+=time.time()-t; calls+=1
        labels=parse(ans,len(items))
        if labels: break
    unp=0
    if not labels: labels=['UNSURE']*len(items); unp=1
    cache_put(k,dict(model=model,labels=labels,unparsed=unp,secs=secs,calls=calls,ans=ans[:300]))
    STATS['called']+=calls
    return labels,unp,secs,calls
def run_arm(model,docs,seed,units,out):
    """label all clauses of docs; returns dict (unit_id,idx)->label ; tallies"""
    allc=[c for u in units.values() if u['document'] in docs for c in clauses_of(u)]
    rng=random.Random(seed); order=list(allc); rng.shuffle(order)
    res={};tot=dict(calls=0,secs=0.0,unparsed=0,batches=0)
    for i in range(0,len(order),4):
        items=order[i:i+4]
        labels,unp,secs,calls=label_batch(model,items)
        for c,l in zip(items,labels): res[(c['unit_id'],c['idx'])]=l
        tot['calls']+=calls;tot['secs']+=secs;tot['unparsed']+=unp;tot['batches']+=1
        if tot['batches']%50==0: print(model,seed,tot['batches'],flush=True)
    json.dump(dict(labels={'%s|%d'%k:v for k,v in res.items()},tot=tot),open(out,'w'))
    return res,tot
