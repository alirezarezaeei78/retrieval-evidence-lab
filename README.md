# Document Evidence Inspector

New 13 November release: compare a batch of queries, inspect token coverage and unsupported fixture matches, and export the same source/index/query snapshot. This is a local lexical search workbench; it does not generate or verify answers.

## Run locally

Python 3.12. Install in an isolated environment:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py --port 8765
```

Open **http://127.0.0.1:8765**. It binds only to loopback; keep it local. No account, API key, pretrained download, hosted service or external document transmission.

1. Keep the eight included authored synthetic documents, or import UTF-8 TXT/Markdown files. Use only data you are authorized to process.
2. For a single query, enter `restore deleted project` and inspect the source span before using it.
3. Click **Load diagnostic queries**, then **Compare both methods**. The 22 known query annotations apply to the included example corpus only.
4. Expand `none-04 · TFIDF`: the two-year-refund question retrieves a 14-day policy. A high lexical match is not proof of support.
5. Download batch JSON and CSV. Both carry query IDs, exact scores/ranks/spans, document hashes, source snapshot, index/config snapshot and request hash. Rejected queries keep a blank-result row in CSV. Exports stream the saved report through a bounded same-origin form, without refitting or reranking.

For your own questions, enter a JSON list such as:

```json
[{"id":"my-query","query":"restore deleted project"}]
```

Omit `relevant_sources` for unlabelled queries. `[]` is an explicit prior annotation that the corpus does not support a query; it is **not** inferred by the model. A nonempty list contains unique source IDs in the selected corpus. Labels affect diagnostics/metrics only, never scoring. The app marks unlabelled relevance and unsupported acceptance as unmeasured.

Limits:1–50 query records, IDs 1–64 ASCII characters, queries 1–1,000 characters;1–20 documents,50,000 UTF-8 bytes each and 500,000 total. Batch retrieval uses the fixed k=3. Invalid input errors do not silently discard a query. Source changes and query edits invalidate old batch exports. Empty/tokenless/unseen-vocabulary cases remain inspectable.

## CLI and reproduction

```sh
python workbench.py --queries examples/batch-queries.json --output local-output/batch
python -m unittest -v test_search test_workbench
python evaluate_workbench.py --output local-output/reproduction-2026-11-13
python render_workbench_figures.py
```

The original single-query CLI is preserved:

```sh
python search.py --query "restore deleted project" --output local-output/single
```

See the frozen [protocol](experiments/2026-11-13/PROTOCOL.md), [input hashes](experiments/2026-11-13/protocol-frozen.json), [actual results](experiments/2026-11-13/results.json), [all 44 reports](experiments/2026-11-13/batch-report.json) and [CSV](experiments/2026-11-13/batch-report.csv). Historical 14 October records remain unchanged; new commands use local-output by default.

## Measured functionality results —13 November 2026

The same 8 authored documents,24 passages and 22 known query fixtures as October, with 2 development queries excluded. These are developer-visible diagnostics, **not independent enterprise validation**. No retrieval model, label, threshold or scoring rule was changed for this integration.

| Outcome on identical queries | Keyword overlap | TF-IDF |
| --- | ---: | ---: |
| Relevant source first |15/16|15/16|
| Macro source Recall@3 |0.9375|1.0000|
| Known unsupported accepted |3/6|3/6|

Each relevant fixture has one source annotation, so these Recall@3 values correspond to 15/16 and 16/16 hits. Keyword accepts any positive unique-query-token overlap; TF-IDF uses 0.15. The score scales and gates are not calibrated to equal acceptance. One fixture difference is not general superiority. Both methods accept the same three unsupported questions: a two-year refund, a legal requirement and an exact recovery guarantee. The passages do not establish those claims.

The new batch route matched the original single-query route for all 44 query–method reports and 79 accepted passages. Independent Python count/smooth-IDF/cosine arithmetic checked 1,056 passage scores, with maximum absolute difference 1.1102230246251565 e-16. JSON/CSV ranks and scores round-trip exactly. Actual desktop native downloads matched all 85 CSV rows and the evaluated JSON; exact displayed decimal strings matched all 79 accepted scores. Correctness checks and retained implementation corrections are in the experiment directory.

## What the snapshots mean

The source hash canonicalizes documents by source ID and includes their title and decoded text. Each passage retains its original source lines and text hash. The index hash additionally includes the declared preprocessing, scikit-learn version, fitted vocabulary/IDF, passage mapping and sparse matrix. The request hash includes query IDs/text/optional annotations, chosen methods and the index hash. Queries never extend vocabulary or fit IDF.

These versioned hashes identify a declared report; they do not prove source truth, answer support or security, and cross-version hash identity is not guaranteed. The original single-search `corpus_sha 256` remains for compatibility and uses its historical serialization; do not compare it to the new versioned source hash.

## Data handling and limitations

Text stays between your browser and the loopback process. No query logs or source files are saved by the server. Exports intentionally save selected reports locally. Literal markup is rendered with textContent; spreadsheet formula-like cells are prefixed in CSV, so those text cells intentionally differ from raw JSON. Fixed download names/Host/Origin/CSP/size checks reduce accidental misuse; this is not a production security audit. Do not expose the development server publicly.

English lexical preprocessing does not reason reliably about negation, quantities, dates or policy conditions. Unicode preservation does not establish multilingual relevance. A no-result status does not prove that no answer exists. The user must inspect source meaning.

Desktop single/batch workflow, local import, malformed/empty input recovery, stale-export prevention and native JSON/CSV parity were verified in Chrome. The requested 390 px override did not apply, so **mobile behavior remains unverified**. No mobile certification, performance improvement, runtime, adoption or business-impact claim is made.

Code, synthetic corpus, query fixtures and original figures are MIT under the owner [LICENSE](LICENSE). Dependencies retain their licences. Primary method sources and version notes: [sources](experiments/2026-11-13/sources.json). No private customer/employer data is included.
