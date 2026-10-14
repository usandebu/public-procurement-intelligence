# public-procurement-intelligence

> **Work in progress.**

Databricks lakehouse over Spanish public procurement: incremental ingestion of the PLACSP tender feed, a medallion model (Bronze/Silver/Gold), and a GenAI layer that parses tender documents and answers questions with citations.

## Status

- [x] Data sources validated (PLACSP Atom feed, tender PDFs)
- [x] Databricks Free Edition capabilities validated
- [ ] Bronze: incremental feed ingestion
- [ ] Silver: parsed and deduplicated tenders
- [ ] Gold + dashboard
- [ ] Document parsing and Vector Search index
- [ ] RAG app with citations and evaluation set
- [ ] Asset Bundle deployment and CI

## Scope

Tenders with CPV 72 (IT services).
