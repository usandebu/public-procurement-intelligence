# Databricks notebook source
# MAGIC %md
# MAGIC # 04 - Download tender documents
# MAGIC
# MAGIC Downloads the legal (PCAP) and technical (PPT) PDFs of the open tenders closest to their deadline into a Volume and records each file in `bronze.document_files`.
# MAGIC
# MAGIC **Reads:** `gold.open_tenders`, `silver.tender_documents`, `bronze.document_files`
# MAGIC
# MAGIC **Writes:** Volume `bronze.tender_pdfs`, `bronze.document_files`

# COMMAND ----------

import os
import sys
from concurrent.futures import ThreadPoolExecutor

from pyspark.sql import functions as F

sys.path.append(os.path.abspath("../src"))

from procurement.documents import doc_id, download_pdf

dbutils.widgets.text("catalog", "procurement")
dbutils.widgets.text("max_tenders", "40")
CATALOG = dbutils.widgets.get("catalog")
MAX_TENDERS = int(dbutils.widgets.get("max_tenders"))
spark.sql(f"USE CATALOG {CATALOG}")

DOCUMENT_KINDS = ("legal", "technical")
VOLUME_DIR = f"/Volumes/{CATALOG}/bronze/tender_pdfs"
DOWNLOAD_WORKERS = 4

# COMMAND ----------

# MAGIC %md
# MAGIC ## Storage

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE VOLUME IF NOT EXISTS bronze.tender_pdfs

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS bronze.document_files (
# MAGIC   doc_id STRING,
# MAGIC   entry_id STRING,
# MAGIC   folder_id STRING,
# MAGIC   kind STRING,
# MAGIC   file_name STRING,
# MAGIC   uri STRING,
# MAGIC   document_hash STRING,
# MAGIC   volume_path STRING,
# MAGIC   size_bytes BIGINT,
# MAGIC   status STRING,
# MAGIC   error STRING,
# MAGIC   downloaded_at TIMESTAMP
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pending documents

# COMMAND ----------

candidates = spark.sql(
    f"""
    SELECT d.entry_id, d.folder_id, d.kind, d.file_name, d.uri, d.document_hash
    FROM (
      SELECT entry_id FROM gold.open_tenders ORDER BY days_to_deadline LIMIT {MAX_TENDERS}
    ) t
    JOIN silver.tender_documents d ON d.entry_id = t.entry_id
    WHERE d.kind IN {DOCUMENT_KINDS} AND d.uri IS NOT NULL
    """
).collect()

downloaded = {
    row.doc_id
    for row in spark.sql(
        "SELECT doc_id FROM bronze.document_files WHERE status = 'downloaded'"
    ).collect()
}

pending = {}
for row in candidates:
    item = row.asDict()
    item["doc_id"] = doc_id(item["uri"], item["document_hash"])
    if item["doc_id"] not in downloaded and item["doc_id"] not in pending:
        pending[item["doc_id"]] = item

print(f"candidate documents: {len(candidates)}")
print(f"already downloaded:  {len(downloaded)}")
print(f"to download:         {len(pending)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Download

# COMMAND ----------

def fetch(item):
    path = f"{VOLUME_DIR}/{item['doc_id']}.pdf"
    try:
        content = download_pdf(item["uri"])
        with open(path, "wb") as file:
            file.write(content)
        return {**item, "volume_path": path, "size_bytes": len(content), "status": "downloaded", "error": None}
    except Exception as error:
        return {**item, "volume_path": None, "size_bytes": None, "status": "failed", "error": str(error)[:500]}


with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
    results = list(pool.map(fetch, pending.values()))

print(f"downloaded: {sum(r['status'] == 'downloaded' for r in results)}")
print(f"failed:     {sum(r['status'] == 'failed' for r in results)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Record the files

# COMMAND ----------

if results:
    schema = (
        "doc_id string, entry_id string, folder_id string, kind string, file_name string, "
        "uri string, document_hash string, volume_path string, size_bytes bigint, "
        "status string, error string"
    )
    columns = [field.split(" ")[0] for field in schema.split(", ")]
    rows = [tuple(r[c] for c in columns) for r in results]
    (
        spark.createDataFrame(rows, schema)
        .withColumn("downloaded_at", F.current_timestamp())
        .createOrReplaceTempView("document_files_batch")
    )
    spark.sql(
        """
        MERGE INTO bronze.document_files t
        USING document_files_batch s
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
# MAGIC SELECT status, kind, count(*) AS documents, round(sum(size_bytes) / 1048576, 1) AS total_mb
# MAGIC FROM bronze.document_files
# MAGIC GROUP BY status, kind
# MAGIC ORDER BY status, kind

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT folder_id, kind, file_name, status, error
# MAGIC FROM bronze.document_files
# MAGIC WHERE status = 'failed'
