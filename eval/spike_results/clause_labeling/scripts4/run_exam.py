import sys,json
sys.path.insert(0,'/home/coder/reqbot-work/scratch/gold2_exam')
import tle
model,seed,tag,cfg=sys.argv[1],int(sys.argv[2]),sys.argv[3],json.loads(sys.argv[4])
assert all(u['document'] in tle.ALLOWED for u in tle.units.values())
res,tot=tle.run_arm(model,cfg,seed,tle.W+'arm_%s.json'%tag)
tle.show(tag,tle.metrics(res)); print(tot,dict(tle.STATS))
