import sys,json,time,hashlib
sys.path.insert(0,'/home/coder/reqbot-work/scratch/gold2_exam'); sys.path.insert(0,'/home/coder/grc-ai-system')
import tle
from services import cleanup
# usage: lc_exam.py SEEDTAG OUTTAG  (35B only, EXAM only via tle)
tag,out=sys.argv[1],sys.argv[2]; model='ornith:35b'
d=json.load(open(tle.W+'arm_%s.json'%tag))['labels']
keep={};secs=0;n=0
for uid,u in tle.units.items():
    for c in tle.CL[uid]:
        key='%s|%d'%(uid,c['idx'])
        if d.get(key,'NOT_REQUIREMENT')=='NOT_REQUIREMENT': continue
        prompt=cleanup.PROMPT.format(passage=u['text'][:cleanup.MAX_PASSAGE_CHARS],quote=c['text'])
        k=hashlib.sha256(('LC\n'+model+'\n'+cleanup.PROMPT_VERSION+'\n'+prompt).encode()).hexdigest()
        r=tle.cache_get(k)
        if not r:
            t=time.time()
            try: ans=cleanup.ollama_call(prompt,model,tle.ollama_url())
            except Exception as e: ans='ERR'; print('err',e,file=sys.stderr)
            r=dict(ans=ans,secs=time.time()-t); tle.cache_put(k,r)
        secs+=r['secs']; n+=1
        keep[key]='NOT_REQUIREMENT' if cleanup.is_junk(r['ans']) else d[key]
        if n%100==0: print(n,flush=True)
full={'%s|%d'%(uid,c['idx']):keep.get('%s|%d'%(uid,c['idx']),'NOT_REQUIREMENT') for uid in tle.units for c in tle.CL[uid]}
json.dump(dict(labels=full,tot=dict(calls=n,secs=secs)),open(tle.W+'arm_%s.json'%out,'w'))
tle.show(out,tle.metrics(full)); print(n,secs)
