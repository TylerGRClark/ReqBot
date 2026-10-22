import json,glob,os,re,collections,sys
def norm(s): return re.sub(r'\s+',' ',s).strip().lower()
def toks(s): return re.findall(r'[a-z0-9]+',s.lower())
def match(a,b,th=0.6):
    na,nb=norm(a),norm(b)
    if na in nb or nb in na: return True
    ta,tb=toks(a),toks(b)
    if not ta or not tb: return False
    c=collections.Counter(tb); ov=0
    for w in ta:
        if c[w]>0: ov+=1;c[w]-=1
    return ov/min(len(ta),len(tb))>=th
units={json.loads(l)['unit_id']:json.loads(l) for l in open('units_gold2.jsonl')}
rows=collections.defaultdict(list)
for l in open('rows_gold2.jsonl'):
    r=json.loads(l); rows[r['unit_id']].append(r['quote'])
A={};B={}
for f in glob.glob('labelA?/labels_*.jsonl'):
    for l in open(f): d=json.loads(l); A[d['unit_id']]=d['obligations']
for f in glob.glob('labelB_codex/out_A_*.txt'):
    for l in open(f):
        if l.strip(): d=json.loads(l); B[d['unit_id']]=d['obligations']
per=collections.defaultdict(collections.Counter); gold={}
verb=collections.Counter()
for uid,u in units.items():
    d=u['document']; a,b=A[uid],B[uid]
    both=[x for x in a if any(match(x,y,0.8) for y in b)]
    gold[uid]=both
    c=per[d]; c['units']+=1; c['A']+=len(a); c['B']+=len(b); c['both']+=len(both)
    c['A_only']+=sum(1 for x in a if not any(match(x,y,0.8) for y in b))
    c['B_only']+=sum(1 for y in b if not any(match(x,y,0.8) for x in a))
    p=norm(u['text'])
    for y in b: verb['B_verbatim']+= norm(y) in p; verb['B_n']+=1
    for x in a: verb['A_verbatim']+= norm(x) in p; verb['A_n']+=1
    # B0
    c['b0_cov']+=sum(1 for x in both if any(match(x,q) for q in rows.get(uid,[])))
    c['b0_rows']+=len(rows.get(uid,[])); c['b0_ok']+=sum(1 for q in rows.get(uid,[]) if any(match(x,q) for x in both))
print("verbatim",dict(verb))
tot=collections.Counter()
for d,c in per.items():
    tot.update(c)
    print(f"{d:18s} units={c['units']} A={c['A']} B={c['B']} both={c['both']} Aonly={c['A_only']} Bonly={c['B_only']} agree(Jaccard-ish)={c['both']/max(1,c['A']+c['B']-c['both']):.2f} B0 recall={c['b0_cov']/max(1,c['both']):.2f} B0 prec={c['b0_ok']/max(1,c['b0_rows']):.2f}")
c=tot; print(f"ALL A={c['A']} B={c['B']} both={c['both']} agree={c['both']/(c['A']+c['B']-c['both']):.2f} B0 recall={c['b0_cov']/c['both']:.3f} prec={c['b0_ok']/c['b0_rows']:.3f}")
json.dump(gold,open('gold_both.json','w'))
