import sys,json,collections,os,ast
from pathlib import Path
sys.dont_write_bytecode=True
R=Path("/home/coder/grc-ai-system")
for p in (R, R/"eval/spike_results/wp_45_7", R/"eval/spike_results/wp_45_1e", R/"eval/spike_results/wp_45_audit"): sys.path.insert(0,str(p))
import score_discovery as SD, chunk_sets as CS
import score as DEV
HERE=os.path.expanduser('~/reqbot-work/scratch/clause_label2/')
T=Path.home()/"reqbot-work/scratch/model_trial"
final,index,obl,pages=SD.load_dev_labels()
DOCS=sorted({index[i]["document"] for i in index})
chunks=CS.load_document_chunks(*DOCS)
dev=CS.dev_chunks()
def units():
    u={}
    for d,c in dev:
        uid='%s|%s'%(d,c['chunk_id'])
        h=c.get('parent_header_text') or ''
        ref=c.get('section_ref_path') or ''
        if isinstance(ref,(list,tuple)): ref=' > '.join(map(str,ref))
        elif ref in ('[]',"['']"): ref=''
        else: ref=str(ref)
        u[uid]=dict(unit_id=uid,document=d,chunk_id=c['chunk_id'],text=c['raw_text'],heading=h,ref=ref)
    return u
def score(records):
    by=collections.defaultdict(list)
    for d,rec in records: by[d].append(rec)
    traces=DEV.trace_all(obl,index,SD.runs_for(by,DOCS),None)
    boot=DEV.page_bootstrap(traces,False,pages=pages)["extracted"]
    found={k for k in obl if traces[k]["status"]["extracted"]!="none"}
    return dict(rec_any=len(found)/len(obl),rec_primary=boot["primary"]["recall"],
      prec=SD.precision_rate(SD.precision_tally(records,final,index)),tally=SD.precision_tally(records,final,index),
      n=len(records),found=found,traces=traces)
