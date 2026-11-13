"""Execute the frozen batch integration protocol and independent score audit."""
import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from search import ROOT, EvidenceIndex, load_documents
from workbench import Workbench, batch_csv


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'local-output/workbench')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    frozen=json.loads((ROOT/'experiments/2026-11-13/protocol-frozen.json').read_text(encoding='utf-8'))
    # The frozen receipt hashes the declared UTF-8 text with LF; Windows stores CRLF.
    protocol_text=(ROOT/'experiments/2026-11-13/PROTOCOL.md').read_text(encoding='utf-8')
    assert hashlib.sha256(protocol_text.encode('utf-8')).hexdigest()==frozen['protocol_sha256']
    for path,expected in frozen['input_sha256'].items():
        assert sha(ROOT/path)==expected,path
    tests=subprocess.run([sys.executable,'-m','unittest','-v','test_search','test_workbench'],
                         cwd=ROOT,text=True,encoding='utf-8',capture_output=True)
    (args.output/'checks-stdout.txt').write_text(tests.stdout+tests.stderr,encoding='utf-8')
    if tests.returncode:
        raise RuntimeError('Checks failed: see checks-stdout.txt')
    docs=load_documents(ROOT/'examples/corpus')
    original=json.loads((ROOT/'examples/queries.json').read_text(encoding='utf-8'))
    queries=json.loads((ROOT/'examples/batch-queries.json').read_text(encoding='utf-8'))
    assert queries==[{k:q[k] for k in ['id','query','relevant_sources']} for q in original['evaluation']]
    workbench=Workbench(docs);report=workbench.batch(queries)
    baseline=EvidenceIndex(docs)
    vocabulary=dict(baseline.vectorizer.vocabulary_)
    # Independent smooth-IDF/count/cosine arithmetic. Analyzer specifies the shared token contract.
    passage_counts=[Counter(baseline.analyzer(p.excerpt)) for p in baseline.passages]
    terms=sorted(vocabulary)
    n=len(passage_counts)
    idf={term:1+math.log((1+n)/(1+sum(term in counts for counts in passage_counts))) for term in terms}

    def vector(counts):
        weights={term:counts[term]*idf[term] for term in counts if term in idf}
        norm=math.sqrt(math.fsum(v*v for v in weights.values()))
        return {term:v/norm for term,v in weights.items()} if norm else {}

    passage_vectors=[vector(c) for c in passage_counts]
    max_error=0.0;parity_rows=0;oracle_rows=0;single_mismatches=0
    for q in report['reports']:
        reference=baseline.search(q['query'],q['method'])
        actual=[{k:v for k,v in row.items() if k!='rank'} for row in q['results']]
        single_mismatches+=actual!=reference['results'] or q['accepted']!=reference['accepted']
        assert actual==reference['results'] and q['accepted']==reference['accepted']
        parity_rows+=len(actual)
        counts=Counter(baseline.analyzer(q['query']));query_vector=vector(counts)
        scores=[]
        for pc,pv in zip(passage_counts,passage_vectors):
            if q['method']=='keyword':
                score=len(set(pc)&set(counts))/len(counts) if counts else 0.0
            else:
                score=math.fsum(value*pv.get(term,0.0) for term,value in query_vector.items())
            scores.append(score)
        raw=(baseline.matrix@baseline.vectorizer.transform([q['query']]).T).toarray().ravel().tolist() if q['method']=='tfidf' else [len(set(pc)&set(counts))/len(counts) if counts else 0.0 for pc in passage_counts]
        max_error=max(max_error,max(abs(a-b) for a,b in zip(raw,scores)))
        assert all(abs(a-b)<=1e-12 for a,b in zip(raw,scores))
        order=sorted(range(n),key=lambda i:(-scores[i],baseline.passages[i].source_id,baseline.passages[i].line_start))
        ids=[baseline.passages[i].passage_id for i in order if scores[i]>0 and scores[i]>=q['threshold']][:3]
        assert ids==[x['passage_id'] for x in q['results']],q['id']
        for row in q['results']:
            i=next(i for i,p in enumerate(baseline.passages) if p.passage_id==row['passage_id'])
            assert abs(scores[i]-row['score'])<=1e-12
            doc=next(d for d in docs if d.source_id==row['source_id'])
            assert row['excerpt']=='\n'.join(doc.text.splitlines()[row['line_start']-1:row['line_end']])
            assert row['document_sha256']==hashlib.sha256(doc.text.encode('utf-8')).hexdigest()
        oracle_rows+=n
    assert vocabulary==baseline.vectorizer.vocabulary_
    exported=batch_csv(report);csvrows=list(csv.DictReader(io.StringIO(exported)))
    expected=[(q,row) for q in report['reports'] for row in q['results'] or [{}]]
    assert len(csvrows)==len(expected)
    for row,(query,match) in zip(csvrows,expected):
        assert row['query_id']==query['id'] and row['method']==query['method']
        assert row['index_snapshot_sha256']==report['index_snapshot_sha256']
        if match:
            assert float(row['score'])==match['score'] and int(row['rank'])==match['rank']
            assert row['excerpt']==match['excerpt']
        else:
            assert row['rank']==row['score']==row['passage_id']==''
    independent=[]
    for method in ['keyword','tfidf']:
        rows=[q for q in report['reports'] if q['method']==method]
        rel=[q for q in rows if q['relevant_sources']]
        unsupported=[q for q in rows if q['relevant_sources']==[]]
        h1=sum(bool(q['results'] and q['results'][0]['source_id'] in q['relevant_sources']) for q in rel)
        recalls=[len({r['source_id'] for r in q['results']}&set(q['relevant_sources']))/len(q['relevant_sources']) for q in rel]
        summary=next(s for s in report['summaries'] if s['method']==method)
        assert summary['hits_at_1']==h1 and summary['macro_source_recall_at_3']==sum(recalls)/len(rel)
        assert summary['unsupported_accepted']==sum(bool(q['results']) for q in unsupported)
        independent.append(dict(method=method,relevant_queries=len(rel),hits_at_1=h1,
                                macro_source_recall_at_3=sum(recalls)/len(rel),unsupported_queries=len(unsupported),
                                unsupported_accepted=sum(bool(q['results']) for q in unsupported)))
    results=dict(executed_at=datetime.now(timezone.utc).isoformat(),
                 classification='New batch app integration; rerun of known authored synthetic fixtures, not independent validation',
                 model_changed=False,documents=len(docs),passages=n,query_count=len(queries),query_method_reports=len(report['reports']),
                 summaries=report['summaries'],independent_summaries=independent,
                 batch_single_query_mismatches=single_mismatches,compared_accepted_passages=parity_rows,
                 independent_passage_scores_checked=oracle_rows,independent_max_absolute_score_error=max_error,
                 csv_rows=len(csvrows),exact_json_csv_rank_score_parity=True,
                 source_snapshot_sha256=report['source_snapshot_sha256'],index_snapshot_sha256=report['index_snapshot_sha256'],
                 protocol=frozen,environment=dict(python=platform.python_version(),platform=platform.platform(),
                    dependencies={x:importlib.metadata.version(x) for x in ['numpy','scipy','scikit-learn','matplotlib','threadpoolctl']}),
                 source_sha256={x:sha(ROOT/x) for x in ['search.py','workbench.py','app.py','evaluate_workbench.py','test_workbench.py','web/ui.js','web/index.html','web/style.css']},
                 unsupported_matches=[dict(id=q['id'],method=q['method'],query=q['query'],top_result=q['results'][0])
                                      for q in report['reports'] if q['relevant_sources']==[] and q['accepted']],
                 limits=['Same known October corpus and22queries; developer-visible diagnostic evidence.',
                         'Thresholds differ by method and are not calibrated to equal acceptance.',
                         'Annotations are supplied fixture labels, never predicted answer support.',
                         'No semantic answer verification, runtime comparison or deployment claim.'])
    for name,data in [('batch-report.json',report),('results.json',results)]:
        (args.output/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (args.output/'batch-report.csv').write_text(exported,encoding='utf-8')
    print(json.dumps(results,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
