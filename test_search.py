"""Correctness, evidence/export and loopback user-workflow checks."""
import copy,csv,hashlib,io,json,math,tempfile,threading,unittest,urllib.request,urllib.error
from dataclasses import asdict
from pathlib import Path
import numpy as np
from app import Handler,ThreadingHTTPServer,LocalServer
from search import ROOT,Document,EvidenceIndex,validate_documents,load_documents,segment,csv_report,safe_cell,TOKEN_PATTERN

def doc(source='alpha',text='alpha beta\nsecond gamma'):
    return {'source_id':source,'title':source,'text':text}

class SearchChecks(unittest.TestCase):
    def setUp(self):self.docs=load_documents(ROOT/'examples/corpus');self.index=EvidenceIndex(self.docs)
    def test_empty_corpus(self):
        with self.assertRaises(ValueError):validate_documents([])
    def test_duplicate_source_id(self):
        with self.assertRaises(ValueError):validate_documents([doc(),doc()])
    def test_invalid_source_id(self):
        for source in ['../secret','Title with spaces','', 'x'*65]:
            with self.subTest(source=source),self.assertRaises(ValueError):validate_documents([doc(source)])
    def test_invalid_schema(self):
        for records in [None,{},[None],[{'source_id':'x'}],[doc(text=42)]]:
            with self.subTest(records=records),self.assertRaises(ValueError):validate_documents(records)
    def test_empty_document(self):
        with self.assertRaises(ValueError):validate_documents([doc(text=' \n\t')])
    def test_title_limits(self):
        for title in ['', ' '*5, 'a'*161]:
            bad=doc();bad['title']=title
            with self.subTest(title=title),self.assertRaises(ValueError):validate_documents([bad])
    def test_document_byte_limit(self):
        with self.assertRaises(ValueError):validate_documents([doc(text='é'*25001)])
    def test_document_count_limit(self):
        with self.assertRaises(ValueError):validate_documents([doc(str(i)) for i in range(21)])
    def test_total_byte_limit(self):
        with self.assertRaises(ValueError):validate_documents([doc(str(i),'a'*50000) for i in range(11)])
    def test_tokenless_corpus(self):
        with self.assertRaises(ValueError):EvidenceIndex(validate_documents([doc(text='!!!')]))
    def test_empty_and_oversized_query(self):
        for q in [None,'',' \n','x'*1001]:
            with self.subTest(q=q),self.assertRaises(ValueError):self.index.search(q)
    def test_invalid_k(self):
        for k in [0,21,True,1.5]:
            with self.subTest(k=k),self.assertRaises(ValueError):self.index.search('backup',k=k)
    def test_invalid_method(self):
        with self.assertRaises(ValueError):self.index.search('backup','semantic')
    def test_invalid_threshold(self):
        for threshold in [-1,2,float('nan'),float('inf'),True,'0.1']:
            with self.subTest(threshold=threshold),self.assertRaises(ValueError):self.index.search('backup',threshold=threshold)
    def test_unknown_vocabulary_rejects(self):
        self.assertFalse(self.index.search('zyxwvuquasar')['accepted'])
    def test_punctuation_only_rejects(self):self.assertFalse(self.index.search('?!...')['accepted'])
    def test_unicode_and_case_equivalence(self):
        ix=EvidenceIndex(validate_documents([doc(text='Café résumé analysis')]))
        a=ix.search('CAFÉ',threshold=0);b=ix.search('cafe',threshold=0)
        self.assertAlmostEqual(a['results'][0]['score'],b['results'][0]['score'])
    def test_inputs_unchanged(self):
        records=[doc()];before=copy.deepcopy(records);ix=EvidenceIndex(validate_documents(records));ix.search('alpha');self.assertEqual(records,before)
    def test_deterministic_ties(self):
        ix=EvidenceIndex(validate_documents([doc('z','identical text'),doc('a','identical text')]))
        self.assertEqual([r['source_id'] for r in ix.search('identical')['results']],['a','z'])
        self.assertEqual(ix.search('identical'),ix.search('identical'))
    def test_exact_spans_and_hashes(self):
        mapping={d.source_id:d for d in self.docs}
        for passage in self.index.passages:
            d=mapping[passage.source_id]
            self.assertEqual(passage.excerpt,'\n'.join(d.text.splitlines()[passage.line_start-1:passage.line_end]))
            self.assertEqual(passage.document_sha256,hashlib.sha256(d.text.encode()).hexdigest())
    def test_long_paragraph_segmentation(self):
        ds=validate_documents([doc(text='\n'.join('line '+str(i) for i in range(19)))])
        ps=segment(ds);self.assertEqual([(p.line_start,p.line_end) for p in ps],[(1,8),(9,16),(17,19)])
    def test_segment_invalid_limit(self):
        with self.assertRaises(ValueError):segment(self.docs,True)
    def test_l2_norm_and_manual_cosine(self):
        ix=EvidenceIndex(validate_documents([doc('a','alpha alpha beta'),doc('b','beta gamma')]))
        v=ix.vectorizer.transform(['alpha beta']).toarray()[0];m=ix.matrix.toarray()
        self.assertTrue(np.allclose(np.linalg.norm(m,axis=1),1))
        result=ix.search('alpha beta',threshold=0)
        for row in result['results']:
            i=next(i for i,p in enumerate(ix.passages) if p.passage_id==row['passage_id'])
            self.assertAlmostEqual(row['score'],float(np.dot(m[i],v)),places=12)
    def test_no_query_vocabulary_leakage(self):
        vocab=dict(self.index.vectorizer.vocabulary_);self.index.search('undocumentedspecialtoken')
        self.assertEqual(vocab,self.index.vectorizer.vocabulary_)
    def test_finite_bounded_scores(self):
        for method in ['tfidf','keyword']:
            for row in self.index.search('source query report',method,threshold=0)['results']:self.assertTrue(math.isfinite(row['score']) and 0<row['score']<=1)
    def test_json_roundtrip(self):
        result=self.index.search('restore deleted project');self.assertEqual(result,json.loads(json.dumps(result,ensure_ascii=False)))
    def test_csv_values_and_excerpt_roundtrip(self):
        report=self.index.search('restore deleted project');rows=list(csv.DictReader(io.StringIO(csv_report(report))))
        for row,result in zip(rows,report['results']):
            self.assertEqual(row['excerpt'],result['excerpt']);self.assertEqual(row['source_id'],result['source_id']);self.assertEqual(float(row['score']),result['score'])
    def test_csv_formula_neutralisation(self):
        for value in ['=SUM(1,2)',' +cmd','-unsafe','@function','\tformula']:self.assertTrue(safe_cell(value).startswith("'"))
        self.assertEqual(safe_cell('ordinary text'),'ordinary text')
    def test_csv_no_results_retains_query(self):
        rows=list(csv.DictReader(io.StringIO(csv_report(self.index.search('unknownzyxwvu')))));self.assertEqual(len(rows),1);self.assertEqual(rows[0]['accepted'],'False')
    def test_invalid_utf8_file(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'bad.txt').write_bytes(b'\xff\xfe')
            with self.assertRaises(ValueError):load_documents(d)
    def test_document_change_changes_fingerprint(self):
        a=EvidenceIndex(validate_documents([doc()]));b=EvidenceIndex(validate_documents([doc(text='different contents')]))
        self.assertNotEqual(a.corpus_sha256,b.corpus_sha256)
    def test_saved_configuration_matches_executed_tokenizer(self):
        config=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
        self.assertEqual(config['token_pattern'],TOKEN_PATTERN)
        self.assertEqual(tuple(config['ngram_range']),self.index.vectorizer.ngram_range)
        self.assertEqual(config['norm'],self.index.vectorizer.norm)
        self.assertEqual(config['smooth_idf'],self.index.vectorizer.smooth_idf)
        self.assertEqual(config['stop_words'],self.index.vectorizer.stop_words)
        self.assertEqual(config['tfidf_threshold'],self.index.search('backup')['threshold'])

class HTTPChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url=f'http://127.0.0.1:{cls.server.server_port}'
        cls.payload={'documents':[asdict(d) for d in load_documents(ROOT/'examples/corpus')],'query':'restore deleted project','method':'tfidf'}
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,path,payload=None,headers=None):
        req=urllib.request.Request(self.url+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with urllib.request.urlopen(req,timeout=10) as r:return r.status,r.read(),r.headers
        except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
    def test_primary_search_and_export_workflow(self):
        status,body,_=self.request('/search',self.payload);self.assertEqual(status,200);report=json.loads(body);expected=EvidenceIndex(load_documents(ROOT/'examples/corpus')).search(self.payload['query']);self.assertEqual(report,expected)
        status,body,_=self.request('/export',self.payload);self.assertEqual(status,200);self.assertEqual(body.decode(),csv_report(report))
    def test_examples_and_static_assets(self):
        status,body,_=self.request('/examples');self.assertEqual(status,200);self.assertEqual(len(json.loads(body)['documents']),8)
        for path in ['/','/ui.js','/style.css']:self.assertEqual(self.request(path)[0],200)
    def test_malformed_document_failure(self):self.assertEqual(self.request('/search',{'documents':[],'query':'alpha'})[0],400)
    def test_cross_origin_rejected(self):self.assertEqual(self.request('/search',self.payload,{'Origin':'https://untrusted.example'})[0],403)
    def test_unexpected_host_rejected(self):self.assertEqual(self.request('/search',self.payload,{'Host':'untrusted.example'})[0],403)
    def test_path_traversal_rejected(self):self.assertEqual(self.request('/../search.py')[0],404)
    def test_content_security_and_no_cache_headers(self):
        _,_,headers=self.request('/');self.assertIn("script-src 'self'",headers['Content-Security-Policy']);self.assertEqual(headers['Cache-Control'],'no-store')
    def test_second_server_cannot_share_the_port(self):
        with self.assertRaises(OSError):LocalServer(('127.0.0.1',self.server.server_port),Handler)

if __name__=='__main__':unittest.main(verbosity=2)
