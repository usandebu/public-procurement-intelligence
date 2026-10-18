# Databricks notebook source
# MAGIC %md
# MAGIC # 05 - Extract page text
# MAGIC
# MAGIC Extracts the text layer of each downloaded PDF page by page. Documents without a usable text layer are marked `needs_ocr`.
# MAGIC
# MAGIC **Reads:** `bronze.document_files`, `silver.document_extractions`, Volume `bronze.tender_pdfs`
# MAGIC
# MAGIC **Writes:** `silver.document_pages`, `silver.document_extractions`

# COMMAND ----------

# MAGIC %pip install pypdf

# COMMAND ----------

import os
import sys

sys.path.append(os.path.abspath("../src"))

from procurement.pdf_text import extract_pages

dbutils.widgets.text("catalog", "procurement")
CATALOG = dbutils.widgets.get("catalog")
spark.sql(f"USE CATALOG {CATALOG}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tables

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS silver

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS silver.document_pages (
# MAGIC   doc_id STRING,
# MAGIC   entry_id STRING,
# MAGIC   folder_id STRING,
# MAGIC   kind STRING,
# MAGIC   file_name STRING,
# MAGIC   page_number INT,
# MAGIC   text STRING,
# MAGIC   char_count INT
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS silver.document_extractions (
# MAGIC   doc_id STRING,
# MAGIC   status STRING,
# MAGIC   pages INT,
# MAGIC   total_chars BIGINT,
# MAGIC   avg_chars_per_page INT,
# MAGIC   error STRING,
# MAGIC   extracted_at TIMESTAMP
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pending documents

# COMMAND ----------

pending = spark.sql(
    """
    SELECT f.doc_id, f.entry_id, f.folder_id, f.kind, f.file_name, f.volume_path
    FROM bronze.document_files f
    LEFT ANTI JOIN silver.document_extractions e ON f.doc_id = e.doc_id
    WHERE f.status = 'downloaded'
    """
).collect()

print(f"documents to extract: {len(pending)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Extract

# COMMAND ----------

page_rows = []
extraction_rows = []

for doc in pending:
    try:
        with open(doc.volume_path, "rb") as file:
            extraction = extract_pages(file.read())
    except Exception as error:
        extraction_rows.append((doc.doc_id, "failed", None, None, None, str(error)[:500]))
        continue

    pages = len(extraction.pages)
    average = extraction.total_chars // pages if pages else 0
    status = "needs_ocr" if extraction.needs_ocr else "extracted"
    extraction_rows.append((doc.doc_id, status, pages, extraction.total_chars, average, None))

    if status == "extracted":
        for page in extraction.pages:
            page_rows.append(
                (
                    doc.doc_id,
                    doc.entry_id,
                    doc.folder_id,
                    doc.kind,
                    doc.file_name,
                    page.page_number,
                    page.text,
                    len(page.text),
                )
            )

print(f"extracted pages:   {len(page_rows)}")
print(f"documents handled: {len(extraction_rows)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write

# COMMAND ----------

if page_rows:
    spark.createDataFrame(
        page_rows,
        "doc_id string, entry_id string, folder_id string, kind string, file_name string, "
        "page_number int, text string, char_count int",
    ).createOrReplaceTempView("document_pages_batch")
    spark.sql(
        """
        MERGE INTO silver.document_pages t
        USING document_pages_batch s
        ON t.doc_id = s.doc_id AND t.page_number = s.page_number
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """
    )

if extraction_rows:
    spark.createDataFrame(
        extraction_rows,
        "doc_id string, status string, pages int, total_chars bigint, "
        "avg_chars_per_page int, error string",
    ).selectExpr("*", "current_timestamp() AS extracted_at").createOrReplaceTempView(
        "document_extractions_batch"
    )
    spark.sql(
        """
        MERGE INTO silver.document_extractions t
        USING document_extractions_batch s
        ON t.doc_id = s.doc_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT status, count(*) AS documents, sum(pages) AS pages, round(avg(avg_chars_per_page)) AS avg_chars_per_page
# MAGIC FROM silver.document_extractions
# MAGIC GROUP BY status

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT kind, count(DISTINCT doc_id) AS documents, count(*) AS pages, sum(char_count) AS characters
# MAGIC FROM silver.document_pages
# MAGIC GROUP BY kind

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT folder_id, file_name, page_number, left(text, 300) AS text_start
# MAGIC FROM silver.document_pages
# MAGIC WHERE page_number = 5
# MAGIC LIMIT 3
