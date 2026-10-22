import json,random,sys,os
sys.path.insert(0,os.path.expanduser('~/reqbot-work/scratch/clause_label'))
from metrics import *
random.seed(20261022)
arms={a:json.load(open(f'arm_exam_{a}.json'))['labels'] for a in ('L8','L35')}
ex=[u for u,x in units.items() if x['document'] in EXAM]
items={}   # key -> dict
def add(uid,text,arm,matched):
    k=(uid,norm(text))
    it=items.setdefault(k,dict(uid=uid,text=text,arms=set(),matched=matched))
    it['arms'].add(arm)
for uid in ex:
    R=reqs[uid]
    for a in ('L8','L35'):
        for t in flagged_texts(uid,arms[a]): add(uid,t,a,any(match(r,t) for r in R))
    for t in rows.get(uid,[]): add(uid,t,'B0',any(match(r,t) for r in R))
allv=list(items.values())
def pick(arm,matched,n):
    pool=[i for i in allv if arm in i['arms'] and i['matched']==matched]; random.shuffle(pool); return pool[:n]
chosen={}
for arm,n in (('L8',40),('L35',30),('B0',30)):
    for i in pick(arm,False,n): chosen[(i['uid'],norm(i['text']))]=i
for i in pick('L8',True,15)+pick('L35',True,15): chosen[(i['uid'],norm(i['text']))]=i
sel=list(chosen.values()); random.shuffle(sel)
blind=[];key=[]
for n,i in enumerate(sel,1):
    u=units[i['uid']]
    blind.append(dict(id=f'Q{n:03d}',document=u['document'],heading=u.get('heading',''),ref=u.get('ref',''),paragraph=u['text'],candidate=i['text']))
    key.append(dict(id=f'Q{n:03d}',uid=i['uid'],arms=sorted(i['arms']),matched_labeled=i['matched']))
json.dump(blind,open('blind/blind_items.json','w'),indent=1); json.dump(key,open('blind/KEY_DO_NOT_SHOW.json','w'),indent=1)
cnt={a:(sum(1 for i in allv if a in i['arms'] and not i['matched']),sum(1 for i in allv if a in i['arms'])) for a in ('L8','L35','B0')}
print(len(sel),cnt)
