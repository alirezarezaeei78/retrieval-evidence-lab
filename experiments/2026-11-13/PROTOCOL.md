# Frozen batch-search integration protocol —13November2026

Freeze before executing the new batch implementation/evaluation. This is a serving and diagnostic integration, not a new retrieval model or an independent quality benchmark.

Question: can one local app batch keep every query status, rank, exact score, source span and index/source snapshot attached consistently through display and JSON/CSV export?

Data: the existing eight owner-authored synthetic MIT documents in examples/corpus and22 known evaluation queries (16 relevant,6 unsupported), excluding2 development queries. Retain unchanged query labels and all unsupported cases. They were exposed in October; reruns remain development-visible functionality evidence. No private data or provider records. No new labels chosen after results.

Baseline: existing unique analysed-query-token overlap (positive score gate>0) versus existing TF-IDF smooth-IDF/L2 word unigrams, English stopwords, Unicode accent stripping, token pattern in config.json; TF-IDF gate0.15. Fit vocabulary and IDF only on the24 document passages. k=3, stable source-ID then line tie order. No tuning, no seed, no latency comparison; CPU fit budget20minutes. Batch limits1–50queries and2declaredmethods. Preserve existing search API/results.

New implementation: one fitted immutable index per request; query-ID validation; optional explicitly supplied relevance-source annotations used for retrospective diagnostics only, never scoring; full token/known-vocabulary/OOV lists and zero-token/no-vocabulary/below-gate/accepted statuses; canonical source hash plus fitted index/config hash; every query retained even with no result. No score interpreted as confidence or entailment. Unlabelled queries must never receive inferred relevance labels.

Metrics: on same22 queries per method, relevant-source hit@1 and macro source Recall@3 over16 labelled relevant queries; unsupported accepted/rejected over6 known unsupported; preserve every report. Compare44batch query-method reports to existing single-query search on exact same index: IDs/rank/source/score/span/text/accepted unchanged. Independently compute TF-IDF smooth-IDF weights with Python counts/math and dot products, keyword-overlap fractions, metric denominators and ranking on all queries; tolerance1e-12 for independent score arithmetic, exact equality for batch/single and JSON/CSV binary-float roundtrip. CSV spreadsheet-safe text intentionally prefixes formula-like cells and documents it.

Workflow/error gates: actual local browser single and batch use; load known diagnostic fixtures; per-query expandable failures; import synthetic Unicode/markup document; unchanged corpus/query inputs; malformed/empty/oversized/duplicate-ID queries and unknown/duplicate annotations; snapshot change on source change and order invariance; stale exports disabled after input change; desktop/mobile layout and native JSON/CSV downloads checked against saved visible report. No external asset/API, no required paid keys, no generated answers. Model hashes are integrity signals, not security certificates.

Figures: original schematic source/index/query-to-export workflow; measured matched results table; actual unsupported matches showing query and exact source passages. Three static PNG with SVG/editable script and alt; no video. Do not imply fewer unsupported matches from diagnostics alone.

Environment: fresh isolated Python3.12 venv with numpy1.26.4/scipy1.13.1/sklearn1.4.2/matplotlib3.10.0/threadpoolctl3.6.0. Record actual versions/platform and all stdout. The previous incompatible scipy1.17.1 requirement is corrected prospectively; historical experiment files stay unchanged.
