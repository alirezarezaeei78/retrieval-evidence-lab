"""Run the declared synthetic functionality fixtures and preserve every outcome."""
import argparse,hashlib,importlib.metadata,json,platform,sys,unittest
from datetime import datetime,timezone
from pathlib import Path
from search import ROOT,load_documents,EvidenceIndex
import test_search

def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'experiments/2026-10-14');args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    suite=unittest.defaultTestLoader.loadTestsFromModule(test_search);tests=unittest.TextTestRunner(verbosity=2,stream=sys.stdout).run(suite)
    if not tests.wasSuccessful():raise SystemExit('Correctness checks failed; do not publish.')
    declared=json.loads((ROOT/'declared-inputs.json').read_text(encoding='utf-8'))
    for n,h in declared['files_sha256'].items():assert sha(ROOT/n)==h,n
    fixtures=json.loads((ROOT/'examples/queries.json').read_text(encoding='utf-8'));index=EvidenceIndex(load_documents(ROOT/'examples/corpus'));outcomes=[];summaries=[]
    for method in ['keyword','tfidf']:
        for q in fixtures['evaluation']:
            report=index.search(q['query'],method);sources=[r['source_id'] for r in report['results']];relevant=q['relevant_sources']
            outcomes.append({'id':q['id'],'kind':q['kind'],'relevant_sources':relevant,'hit_at_1':bool(relevant and sources and sources[0] in relevant),'hit_at_3':bool(relevant and set(sources)&set(relevant)),**report})
        rows=[r for r in outcomes if r['method']==method];rel=[r for r in rows if r['kind']=='relevant'];none=[r for r in rows if r['kind']=='unsupported']
        summaries.append({'method':method,'relevant_queries':len(rel),'hits_at_1':sum(r['hit_at_1'] for r in rel),'hits_at_3':sum(r['hit_at_3'] for r in rel),'rejected_relevant':sum(not r['accepted'] for r in rel),'unsupported_queries':len(none),'unsupported_accepted':sum(r['accepted'] for r in none),'unsupported_rejected':sum(not r['accepted'] for r in none)})
    result={'executed_at':datetime.now(timezone.utc).isoformat(),'classification':'Authored synthetic fixture testing; no independent validation','documents':len(index.documents),'passages':len(index.passages),'evaluation_queries':len(fixtures['evaluation']),'development_queries_not_scored':[q['id'] for q in fixtures['development']],'checks_passed':tests.testsRun-len(tests.skipped),'checks_skipped':len(tests.skipped),'method_summary':summaries,'parameters':json.loads((ROOT/'config.json').read_text(encoding='utf-8')),'input_files_sha256':declared['files_sha256'],'source_code_sha256':{n:sha(ROOT/n) for n in ['search.py','app.py','test_search.py','evaluate.py']},'environment':{'python':platform.python_version(),'platform':platform.system(),'dependencies':{n:importlib.metadata.version(n) for n in ['numpy','scipy','scikit-learn','matplotlib','threadpoolctl']}},'command':'python evaluate.py --output experiments/2026-10-14','limitations':['Eight synthetic documents and hand-authored queries; no independent validation.','Fixed uncalibrated lexical gates and incomparable score scales; no automatic optimal policy.','Lexical matching does not establish entailment, completeness or legal/semantic correctness.','No generated answers, hosted demo, runtime comparison, deployment or business-impact claim.']}
    (args.output/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');(args.output/'query-results.json').write_text(json.dumps(outcomes,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
