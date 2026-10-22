import sys,json,time
sys.path.insert(0,'.')
from cl import *
import metrics
# usage: run.py MODEL SEED TAG [--exam]   (exam refused unless --exam given)
model,seed,tag=sys.argv[1],int(sys.argv[2]),sys.argv[3]
docs=metrics.EXAM if '--exam' in sys.argv else metrics.TUNE
units,rows,reqs=load_all()
t=time.time()
res,tot=run_arm(model,docs,seed,units,HERE+'arm_%s.json'%tag)
tot['wall']=time.time()-t
d=json.load(open(HERE+'arm_%s.json'%tag)); d['tot']=tot; json.dump(d,open(HERE+'arm_%s.json'%tag,'w'))
m=metrics.metrics(d['labels'],docs)
metrics.show(tag,m); print(tot, dict(STATS))
