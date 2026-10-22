import sys,json,time
sys.path.insert(0,'.')
from cl import *
import common
model,seed,tag=sys.argv[1],int(sys.argv[2]),sys.argv[3]
u=common.units()
t=time.time()
res,tot=run_arm(model,{'afman17-2101','DODI 8410.03','NIST.SP.800-125'},seed,u,HERE+'arm_%s.json'%tag)
tot['wall']=time.time()-t
d=json.load(open(HERE+'arm_%s.json'%tag)); d['tot']=tot; json.dump(d,open(HERE+'arm_%s.json'%tag,'w'))
print(tag,tot,dict(STATS))
