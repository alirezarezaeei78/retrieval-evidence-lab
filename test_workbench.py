"""Batch, snapshot, error and export regression checks on authored fixtures."""
import copy
import csv
import io
import json
import threading
import unittest
import urllib.error
import urllib.request
from urllib.parse import urlencode

from app import Handler, ThreadingHTTPServer
from search import ROOT, Document, load_documents, validate_documents
from workbench import Workbench, batch_csv


class BatchChecks(unittest.TestCase):
    def setUp(self):
        self.documents = load_documents(ROOT / 'examples/corpus')
        self.workbench = Workbench(self.documents)
        self.queries = json.loads((ROOT / 'examples/batch-queries.json').read_text(encoding='utf-8'))

    def test_every_single_result_preserved(self):
        report = self.workbench.batch(self.queries)
        self.assertEqual(len(report['reports']), 44)
        for q in report['reports']:
            expected = self.workbench.index.search(q['query'], q['method'])
            for key in expected:
                if key != 'results':
                    self.assertEqual(q[key], expected[key])
            self.assertEqual([{k:v for k,v in r.items() if k != 'rank'} for r in q['results']], expected['results'])

    def test_known_annotations_do_not_change_ranking(self):
        a = self.workbench.batch([dict(id='q', query='restore deleted project')])
        b = self.workbench.batch([dict(id='q', query='restore deleted project', relevant_sources=[])])
        self.assertEqual([q['results'] for q in a['reports']], [q['results'] for q in b['reports']])
        self.assertNotEqual(a['request_sha256'], b['request_sha256'])

    def test_unlabelled_is_not_known_unsupported(self):
        r = self.workbench.batch([dict(id='q', query='refund after two years')])
        self.assertTrue(all(q['diagnostics']['annotation'] == 'unlabelled' for q in r['reports']))
        self.assertTrue(all(s['unsupported_queries'] == 0 and s['macro_source_recall_at_3'] is None for s in r['summaries']))

    def test_no_result_statuses_and_csv_rows(self):
        r = self.workbench.batch([dict(id='tokens',query='the and'), dict(id='oov',query='zyxwvutquasar')])
        self.assertEqual([q['diagnostics']['status'] for q in r['reports']],
                         ['no_analyzed_tokens','no_analyzed_tokens','no_corpus_vocabulary','no_corpus_vocabulary'])
        self.assertEqual(len(list(csv.DictReader(io.StringIO(batch_csv(r))))), 4)

    def test_invalid_queries_and_limits(self):
        for bad in [None, {}, [], [None], [dict(id='../bad',query='x')],
                    [dict(id='a',query='')], [dict(id='a',query='x'*1001)],
                    [dict(id='a',query='hi',unknown='x')],
                    [dict(id='a',query='hi')]*2,
                    [dict(id=str(i),query='hi') for i in range(51)]]:
            with self.subTest(bad=str(bad)[:100]), self.assertRaises(ValueError):
                self.workbench.batch(bad)

    def test_annotation_errors(self):
        for labels in [None, 'backup', [None], ['missing'], ['backup','backup']]:
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                self.workbench.batch([dict(id='q',query='backup',relevant_sources=labels)])

    def test_invalid_methods(self):
        for methods in [[], 'tfidf', ['semantic'], ['tfidf','tfidf'], [None]]:
            with self.subTest(methods=methods), self.assertRaises(ValueError):
                self.workbench.batch(self.queries, methods)

    def test_source_order_invariance(self):
        other = Workbench(tuple(reversed(self.documents)))
        self.assertEqual(self.workbench.batch(self.queries), other.batch(self.queries))

    def test_content_and_title_change_hashes(self):
        for field in ['text','title']:
            changed = list(self.documents)
            item = changed[0]
            changed[0] = Document(item.source_id, item.title + (' changed' if field=='title' else ''),
                                  item.text + ('\nchanged' if field=='text' else ''))
            other = Workbench(changed)
            self.assertNotEqual(self.workbench.source_snapshot_sha256, other.source_snapshot_sha256)
            self.assertNotEqual(self.workbench.index_snapshot_sha256, other.index_snapshot_sha256)

    def test_query_does_not_refit_or_change_hash(self):
        initial = self.workbench.index_snapshot_sha256
        vocab = dict(self.workbench.index.vectorizer.vocabulary_)
        self.workbench.batch([dict(id='q',query='unseenquasarword')])
        self.assertEqual(initial, self.workbench.index_snapshot_sha256)
        self.assertEqual(vocab,self.workbench.index.vectorizer.vocabulary_)

    def test_query_inputs_unchanged(self):
        before = copy.deepcopy(self.queries)
        self.workbench.batch(self.queries)
        self.assertEqual(before,self.queries)

    def test_json_csv_exact_scores_ranks_and_sources(self):
        report = self.workbench.batch(self.queries)
        self.assertEqual(report,json.loads(json.dumps(report)))
        rows=list(csv.DictReader(io.StringIO(batch_csv(report))))
        expected=[(q,r) for q in report['reports'] for r in q['results'] or [{}]]
        self.assertEqual(len(rows),len(expected))
        for csvrow,(query,row) in zip(rows,expected):
            self.assertEqual(csvrow['query_id'],query['id'])
            self.assertEqual(csvrow['index_snapshot_sha256'],report['index_snapshot_sha256'])
            self.assertEqual(csvrow['excerpt'],row.get('excerpt',''))
            if row:
                self.assertEqual(float(csvrow['score']),row['score'])
                self.assertEqual(int(csvrow['rank']),row['rank'])

    def test_formula_text_protected(self):
        r=self.workbench.batch([dict(id='q',query='=restore deleted project')])
        self.assertTrue(list(csv.DictReader(io.StringIO(batch_csv(r))))[0]['query'].startswith("'="))

    def test_multi_source_recall_denominator(self):
        r=self.workbench.batch([dict(id='q',query='restore deleted project',relevant_sources=['backup','invoice'])])
        for q in r['reports']:
            expected=len({x['source_id'] for x in q['results']}&{'backup','invoice'})/2
            self.assertEqual(q['diagnostics']['source_recall_at_3'],expected)

    def test_unicode_and_markup_preserved(self):
        w=Workbench(validate_documents([dict(source_id='demo',title='Café',text='<script>alert(1)</script>\nCafé résumé retrieval')]))
        r=w.batch([dict(id='unicode',query='CAFE')])
        self.assertTrue(all(q['accepted'] for q in r['reports']))
        self.assertIn('<script>',r['reports'][0]['results'][0]['excerpt'])


class BatchHTTPChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def request(self, data):
        req=urllib.request.Request(self.url+'/batch',data=data,headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=10) as response:return response.status,response.read()
        except urllib.error.HTTPError as error:return error.code,error.read()

    def test_http_report_and_csv_same_snapshot(self):
        docs=[dict(source_id='a',title='A',text='alpha beta')]
        queries=[dict(id='q',query='alpha'),dict(id='oov',query='unknown')]
        status,body=self.request(json.dumps(dict(documents=docs,queries=queries)).encode())
        self.assertEqual(status,200);data=json.loads(body)
        expected=Workbench(validate_documents(docs)).batch(queries)
        self.assertEqual(data['report'],expected);self.assertEqual(data['csv'],batch_csv(expected))

    def test_malformed_requests(self):
        for data in [b'{',b'[]',b'{}',b'\xff']:
            self.assertEqual(self.request(data)[0],400)

    def test_fixture_loader(self):
        with urllib.request.urlopen(self.url+'/batch-examples',timeout=5) as response:
            data=json.load(response)
        self.assertEqual(len(data['queries']),22)
        self.assertNotIn('kind',data['queries'][0])

    def test_native_download_echoes_saved_report_without_refit(self):
        report=Workbench(load_documents(ROOT/'examples/corpus')).batch([dict(id='q',query='restore deleted project')])
        for kind,text in [('json',json.dumps(report,ensure_ascii=False)),('csv',batch_csv(report))]:
            data=urlencode({'format':kind,'content':text}).encode('utf-8')
            req=urllib.request.Request(self.url+'/download',data=data,headers={'Content-Type':'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req,timeout=5) as response:
                self.assertEqual(response.read().decode('utf-8'),text)
                self.assertIn('attachment;',response.headers['Content-Disposition'])

    def test_download_rejects_invalid_format(self):
        req=urllib.request.Request(self.url+'/download',data=urlencode({'format':'html','content':'x'}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(req,timeout=5)
        self.assertEqual(raised.exception.code,400)


if __name__=='__main__':
    unittest.main(verbosity=2)
