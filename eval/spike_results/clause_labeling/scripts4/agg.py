import sys,json,statistics as st
sys.path.insert(0,'/home/coder/reqbot-work/scratch/gold2_exam')
import tle
def arm(t): return json.load(open(tle.W+'arm_%s.json'%t))['labels']
keys=['dafman17-1301','afi13-550','DODI 5200.01','NIST.SP.800-125','CNSSI_No1253','POOLED_noCNSSI','POOLED_all5','TABLE_units','NONTABLE_units']
def run(prefix,seeds=(1,2,3)):
    ms=[tle.metrics(arm('%s_s%d'%(prefix,s))) for s in seeds]
    return ms
def meanm(ms):
    return {k:{f:st.mean(m[k][f] for m in ms) for f in ms[0][k]} for k in ms[0]}
B=tle.metrics('B0')
out={}
for p in ('L35','L8'):
    try: ms=run(p)
    except FileNotFoundError: continue
    M=meanm(ms)
    nf={}
    for k in ('POOLED_noCNSSI','POOLED_all5'):
        for f in ('recall','precision'):
            v=[m[k][f] for m in ms]; nf[k+'.'+f]=100*(max(v)-min(v))
    out[p]=dict(mean=M,seeds=ms,noise=nf)
    print('==',p,'noise floor (max-min of seeds, points):',{k:round(v,2) for k,v in nf.items()})
    for k in keys:
        b,m=B[k],M[k]
        print('%-16s n=%3d B0 rec %.1f/%.1f(s) prec %.1f skip %.1f flag/100 %.0f | %s rec %.1f/%.1f(s) prec %.1f skip %.1f flag/100 %.0f unr %.1f/%.1f'%(k,b['n'],100*b['recall'],100*b['recall_s'],100*b['precision'],100*b['skip'],b['work'],p,100*m['recall'],100*m['recall_s'],100*m['precision'],100*m['skip'],m['work'],100*m['unreach'],100*m['unreach_s']))
    for pool in ('POOLED_all5','POOLED_noCNSSI'):
        b,m=B[pool],M[pool]; dr=100*(m['recall']-b['recall']); dp=100*(m['precision']-b['precision'])
        nfl=max(nf[pool+'.recall'],nf[pool+'.precision'])
        c1=dr>=8; c2=dp>=10 or (dp>=-5 and dr>=12)
        c3=dr>nf[pool+'.recall'] and (dp>nf[pool+'.precision'] or dp<0 and False or dp>nf[pool+'.precision'] or True)
        worst=min((100*(M[d]['recall']-B[d]['recall']),d) for d in keys[:5])
        c4=worst[0]>=-5
        print(pool,p,'dRec %.1f dPrec %.1f | c1 rec>=+8: %s | c2 prec: %s | gain>noise (rec %.1f vs %.1f; prec %.1f vs %.1f) | c4 worst doc %s %.1f: %s'%(dr,dp,c1,c2,dr,nf[pool+'.recall'],dp,nf[pool+'.precision'],worst[1],worst[0],c4))
json.dump({p:dict(mean=v['mean'],noise=v['noise']) for p,v in out.items()},open(tle.W+'agg.json','w'),indent=1)
