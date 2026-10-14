# Implementation record

The protocol and fixtures were declared before the first run. The initial 38-check outcomes are preserved in `first-run-results.json`. A configuration serialization defect escaped the token pattern twice in the metadata; the executed tokenizer was already correct. The metadata was repaired and a configuration parity check added. The 39-check revision is preserved in `revision2-results.json`.

Windows-created input files originally used CRLF bytes. Files were canonicalized to LF before final publication, and the declared byte hashes were updated in revision three. Decoded text, methods, thresholds, labels and ranks were unchanged. Original declarations are preserved. All fixtures had already been observed, so the rerun remains exploratory functionality checking, not fresh independent validation.

A Windows local-runner defect allowed multiple server instances to share a port. The loopback runner now uses an exclusive socket on Windows; an added check verifies that a second instance fails. The final evaluation ran 40 checks with zero skips, with unchanged retrieval counts. No threshold or method tuning was performed to improve those counts.

Browser implementation repairs used Markdown headings for display titles and disabled corpus/query/method changes during asynchronous operations, preventing stale exports or mismatched displayed inputs. Native JSON and CSV downloads were compared with the saved CLI report. A browser download-capture helper timed out, but the actual downloaded bytes were independently verified. Narrow-layout geometry passed; its screenshot capture was unavailable. These limitations are recorded rather than described as a complete accessibility audit.
