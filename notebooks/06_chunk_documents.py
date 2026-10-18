# Databricks notebook source
# MAGIC %md
# MAGIC # 06 - Chunk documents
# MAGIC
# MAGIC Cleans the extracted pages (repeated headers and table-of-contents pages removed) and splits each document into overlapping chunks that keep their page range. The table has Change Data Feed enabled for the Vector Search index.
# MAGIC
# MAGIC **Reads:** `silver.document_pages`, `silver.tenders`, `silver.document_chunks`
# MAGIC
# MAGIC **Writes:** `silver.document_chunks`

# COMMAND ----------

import os
import sys
from itertools import groupby

sys.path.append(os.path.abspath("../src"))

from procurement.chunking import chunk_pages, clean_pages
from procurement.pdf_text import PageText

dbutils.widgets.text("catalog", "procurement")
CATALOG = dbutils.widgets.get("catalog")
spark.sql(f"USE CATALOG {CATALOG}")

CHUNK_CHARS = 1000
OVERLAP_CHARS = 150
KIND_LABELS = {
    "legal": "Pliego de cláusulas administrativas (PCAP)",
    "technical": "Pliego de prescripciones técnicas (PPT)",
}

# COMMAND ----------

# MAGIC %md
# MAGIC ## Table

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS silver.document_chunks (
# MAGIC   chunk_id STRING,
# MAGIC   doc_id STRING,
# MAGIC   entry_id STRING,
# MAGIC   folder_id STRING,
# MAGIC   kind STRING,
# MAGIC   file_name STRING,
# MAGIC   tender_title STRING,
# MAGIC   organ_name STRING,
# MAGIC   detail_url STRING,
# MAGIC   chunk_index INT,
# MAGIC   page_start INT,
# MAGIC   page_end INT,
# MAGIC   text STRING,
# MAGIC   embed_text STRING,
# MAGIC   char_count INT
# MAGIC ) USING DELTA
# MAGIC TBLPROPERTIES (delta.enableChangeDataFeed = true)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pending documents

# COMMAND ----------

pages = spark.sql(
    """
    SELECT p.doc_id, p.entry_id, p.folder_id, p.kind, p.file_name, p.page_number, p.text,
           t.title AS tender_title, t.organ_name, t.detail_url
    FROM silver.document_pages p
    LEFT ANTI JOIN silver.document_chunks c ON p.doc_id = c.doc_id
    LEFT JOIN silver.tenders t ON p.entry_id = t.entry_id
    ORDER BY p.doc_id, p.page_number
    """
).collect()

print(f"pages to chunk: {len(pages)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Chunk

# COMMAND ----------

chunk_rows = []

for doc_id, doc_pages in groupby(pages, key=lambda row: row.doc_id):
    doc_pages = list(doc_pages)
    first = doc_pages[0]
    cleaned = clean_pages([PageText(row.page_number, row.text) for row in doc_pages])
    label = KIND_LABELS.get(first.kind, first.kind)
    header = f"{label} | {first.tender_title} | {first.organ_name}"

    for chunk in chunk_pages(cleaned, CHUNK_CHARS, OVERLAP_CHARS):
        chunk_rows.append(
            (
                f"{doc_id}-{chunk.chunk_index}",
                doc_id,
                first.entry_id,
                first.folder_id,
                first.kind,
                first.file_name,
                first.tender_title,
                first.organ_name,
                first.detail_url,
                chunk.chunk_index,
                chunk.page_start,
                chunk.page_end,
                chunk.text,
                f"{header}\n{chunk.text}",
                len(chunk.text),
            )
        )

print(f"chunks: {len(chunk_rows)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write

# COMMAND ----------

if chunk_rows:
    (
        spark.createDataFrame(
            chunk_rows,
            "chunk_id string, doc_id string, entry_id string, folder_id string, kind string, "
            "file_name string, tender_title string, organ_name string, detail_url string, "
            "chunk_index int, page_start int, page_end int, text string, embed_text string, "
            "char_count int",
        )
        .write.mode("append")
        .saveAsTable("silver.document_chunks")
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT kind, count(DISTINCT doc_id) AS documents, count(*) AS chunks,
# MAGIC        round(avg(char_count)) AS avg_chars, max(char_count) AS max_chars
# MAGIC FROM silver.document_chunks
# MAGIC GROUP BY kind

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) AS chunks, count(DISTINCT chunk_id) AS distinct_chunks
# MAGIC FROM silver.document_chunks

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT folder_id, kind, page_start, page_end, left(embed_text, 400) AS sample
# MAGIC FROM silver.document_chunks
# MAGIC WHERE chunk_index = 4
# MAGIC LIMIT 3
