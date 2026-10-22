import sys,json,time,hashlib
sys.path.insert(0,'.'); sys.path.insert(0,'/home/coder/grc-ai-system')
from cl import *
import metrics as M
from services import cleanup
# usage: lc.py LABEL_ARM_TAG OUTTAG   (TUNE only)
tag,out=sys.argv[1],sys.argv[2]
DOCS=M.EXAM if '--exam' in sys.argv else M.TUNE
model='ornith:35b'
d=json.load(open('arm_%s.json'%tag))['labels']
units,rows,reqs=load_all()
keep={};secs=0;n=0
for uid,u in units.items():
    if u['document'] not in DOCS: continue
    for c in clauses_of(u):
        key='%s|%d'%(uid,c['idx'])
        if d.get(key,'NOT_REQUIREMENT')=='NOT_REQUIREMENT': continue
        prompt=cleanup.PROMPT.format(passage=u['text'][:cleanup.MAX_PASSAGE_CHARS],quote=c['text'])
        k=hashlib.sha256(('LC\n'+model+'\n'+cleanup.PROMPT_VERSION+'\n'+prompt).encode()).hexdigest()
        r=cache_get(k)
        if not r:
            t=time.time()
            try: ans=cleanup.ollama_call(prompt,model,ollama_url())
            except Exception as e: ans='ERR'; print('err',e,file=sys.stderr)
            r=dict(ans=ans,secs=time.time()-t); cache_put(k,r)
        secs+=r['secs']; n+=1
        keep[key]='NOT_REQUIREMENT' if cleanup.is_junk(r['ans']) else d[key]
        if n%100==0: print(n,flush=True)
full={'%s|%d'%(uid,c['idx']):keep.get('%s|%d'%(uid,c['idx']),'NOT_REQUIREMENT') for uid,u in units.items() if u['document'] in DOCS for c in clauses_of(u)}
json.dump(dict(labels=full,tot=dict(calls=n,secs=secs)),open('arm_%s.json'%out,'w'))
M.show(out,M.metrics(full,DOCS)); print(n,secs)
