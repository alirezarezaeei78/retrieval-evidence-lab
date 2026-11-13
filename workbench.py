"""Batch lexical evidence with explicit diagnostics and frozen snapshot metadata."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import re
from dataclasses import asdict
from pathlib import Path

from search import ROOT, EvidenceIndex, load_documents, safe_cell

METHODS = ('keyword', 'tfidf')
MAX_QUERIES = 50


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


class Workbench:
    def __init__(self, documents):
        # Import order must not change a snapshot or tie order.
        self.index = EvidenceIndex(sorted(documents, key=lambda d: d.source_id))
        ix = self.index
        self.sources = [dict(source_id=d.source_id, title=d.title,
                             document_sha256=hashlib.sha256(d.text.encode('utf-8')).hexdigest())
                        for d in ix.documents]
        self.source_snapshot_sha256 = digest([asdict(d) for d in ix.documents])
        self.configuration = dict(methods=list(METHODS), k=3, tfidf_threshold=0.15,
                                  keyword_threshold=0.0, token_pattern=ix.vectorizer.token_pattern,
                                  ngram_range=[1, 1], stop_words='english', strip_accents='unicode',
                                  norm='l2', smooth_idf=True, sublinear_tf=False,
                                  sklearn_version=importlib.metadata.version('scikit-learn'),
                                  tie_policy='score descending, source_id ascending, line_start ascending')
        self.index_snapshot_sha256 = digest(dict(
            source_snapshot_sha256=self.source_snapshot_sha256, configuration=self.configuration,
            passages=[asdict(p) for p in ix.passages],
            vocabulary=ix.vectorizer.vocabulary_, idf=ix.vectorizer.idf_.tolist(),
            matrix=dict(shape=list(ix.matrix.shape), data=ix.matrix.data.tolist(),
                        indices=ix.matrix.indices.tolist(), indptr=ix.matrix.indptr.tolist())))

    def validate_queries(self, records):
        if not isinstance(records, list) or not 1 <= len(records) <= MAX_QUERIES:
            raise ValueError('Provide 1–50 query records.')
        allowed_sources = {d.source_id for d in self.index.documents}
        seen = set()
        clean = []
        for record in records:
            if not isinstance(record, dict) or set(record) - {'id', 'query', 'relevant_sources'}:
                raise ValueError('Query fields are id, query and optional relevant_sources.')
            qid = record.get('id')
            if not isinstance(qid, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', qid):
                raise ValueError('Each query needs a 1–64 character ASCII ID.')
            if qid in seen:
                raise ValueError('Duplicate query ID: ' + qid)
            text = record.get('query')
            if not isinstance(text, str) or not text.strip() or len(text) > 1000:
                raise ValueError('Each query needs 1–1,000 characters.')
            labels = record.get('relevant_sources')
            if 'relevant_sources' in record and (not isinstance(labels, list) or
                    any(not isinstance(x, str) or x not in allowed_sources for x in labels) or
                    len(set(labels)) != len(labels)):
                raise ValueError('Annotations must list unique source IDs present in this corpus.')
            clean.append(dict(id=qid, query=text, relevant_sources=labels))
            seen.add(qid)
        return clean

    def batch(self, queries, methods=None):
        queries = self.validate_queries(queries)
        methods = list(METHODS) if methods is None else methods
        if (not isinstance(methods, list) or not methods or
                any(x not in METHODS for x in methods) or len(set(methods)) != len(methods)):
            raise ValueError('Choose keyword and/or tfidf once each.')
        reports = []
        vocabulary = set(self.index.vectorizer.vocabulary_)
        for q in queries:
            tokens = sorted(set(self.index.analyzer(q['query'])))
            known = sorted(set(tokens) & vocabulary)
            for method in methods:
                report = self.index.search(q['query'], method=method, k=3)
                # Probe ungated scores only to distinguish a gate rejection from no overlap.
                positive = self.index.search(q['query'], method=method, k=3, threshold=0)['accepted']
                state = ('no_analyzed_tokens' if not tokens else 'no_corpus_vocabulary' if not known
                         else 'accepted' if report['accepted'] else 'below_gate' if positive else 'no_positive_overlap')
                labels = q['relevant_sources']
                ranked = [x['source_id'] for x in report['results']]
                diagnostics = dict(status=state, analyzed_terms=tokens, known_terms=known,
                                   oov_terms=sorted(set(tokens) - vocabulary),
                                   annotation=('unlabelled' if labels is None else
                                               'known_unsupported' if not labels else 'known_relevant'),
                                   hit_at_1=None, source_recall_at_3=None,
                                   review=('Unlabelled lexical match; inspect source meaning.' if labels is None else
                                           'Accepted despite an unsupported annotation.' if not labels and ranked else
                                           'No accepted passage.' if not ranked else 'Inspect annotation and exact source.'))
                if labels:
                    diagnostics['hit_at_1'] = bool(ranked and ranked[0] in labels)
                    diagnostics['source_recall_at_3'] = len(set(ranked) & set(labels)) / len(labels)
                for rank, row in enumerate(report['results'], 1):
                    row['rank'] = rank
                reports.append(dict(id=q['id'], relevant_sources=labels, diagnostics=diagnostics, **report))
        summaries = []
        for method in methods:
            rows = [x for x in reports if x['method'] == method]
            relevant = [x for x in rows if x['relevant_sources']]
            unsupported = [x for x in rows if x['relevant_sources'] == []]
            summaries.append(dict(method=method, queries=len(rows), accepted=sum(x['accepted'] for x in rows),
                                  relevant_queries=len(relevant), hits_at_1=sum(x['diagnostics']['hit_at_1'] for x in relevant),
                                  macro_source_recall_at_3=(sum(x['diagnostics']['source_recall_at_3'] for x in relevant) / len(relevant)
                                                           if relevant else None),
                                  unsupported_queries=len(unsupported),
                                  unsupported_accepted=sum(x['accepted'] for x in unsupported)))
        return dict(schema_version=1, source_snapshot_sha256=self.source_snapshot_sha256,
                    index_snapshot_sha256=self.index_snapshot_sha256,
                    request_sha256=digest(dict(queries=queries, methods=methods,
                                               index_snapshot_sha256=self.index_snapshot_sha256)),
                    configuration=self.configuration, sources=self.sources,
                    document_count=len(self.index.documents), passage_count=len(self.index.passages),
                    query_count=len(queries), summaries=summaries, reports=reports,
                    warning='Lexical scores are not answer confidence. Optional annotations are development-visible labels, not model judgments.')


def batch_csv(report):
    fields = ['query_id', 'query', 'method', 'accepted', 'diagnostic_status', 'annotation',
              'source_snapshot_sha256', 'index_snapshot_sha256', 'request_sha256', 'rank',
              'passage_id', 'source_id', 'line_start', 'line_end', 'score', 'matched_terms',
              'document_sha256', 'excerpt']
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fields, lineterminator='\n')
    writer.writeheader()
    for query in report['reports']:
        for row in query['results'] or [{}]:
            item = dict(query_id=query['id'], query=query['query'], method=query['method'], accepted=query['accepted'],
                        diagnostic_status=query['diagnostics']['status'], annotation=query['diagnostics']['annotation'],
                        **{k: report[k] for k in ['source_snapshot_sha256', 'index_snapshot_sha256', 'request_sha256']},
                        **{k: row.get(k, '') for k in fields[9:]})
            if isinstance(item['matched_terms'], list):
                item['matched_terms'] = ' '.join(item['matched_terms'])
            writer.writerow({k: safe_cell(v) for k, v in item.items()})
    return out.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--documents', type=Path, default=ROOT / 'examples/corpus')
    parser.add_argument('--queries', type=Path, required=True, help='JSON list of query records')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = Workbench(load_documents(args.documents)).batch(json.loads(args.queries.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    args.output.with_suffix('.csv').write_text(batch_csv(report), encoding='utf-8')
    print(json.dumps(report['summaries'], indent=2))


if __name__ == '__main__':
    main()
