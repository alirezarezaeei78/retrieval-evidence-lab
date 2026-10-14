# Search cache notes

A cached search result must include the document content hash.
When a document changes, invalidate results linked to its old hash.

A deleted document must no longer appear in retrieved passages.
Rebuild the local index after adding, editing or removing source documents.
