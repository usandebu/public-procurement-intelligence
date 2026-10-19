# Databricks notebook source
# MAGIC %md
# MAGIC # 10 - Export tender catalog
# MAGIC
# MAGIC Writes a JSON catalog of the tenders that have indexed documents, used by the app to fill its tender selector.
# MAGIC
# MAGIC **Reads:** `silver.document_chunks`, `silver.tenders`
# MAGIC
# MAGIC **Writes:** Volume `gold.app_data` (`tender_catalog.json`)

# COMMAND ----------

import json

dbutils.widgets.text("catalog", "procurement")
CATALOG = dbutils.widgets.get("catalog")
spark.sql(f"USE CATALOG {CATALOG}")

CATALOG_PATH = f"/Volumes/{CATALOG}/gold/app_data/tender_catalog.json"

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS gold

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE VOLUME IF NOT EXISTS gold.app_data

# COMMAND ----------

rows = spark.sql(
    """
    SELECT
      c.entry_id,
      c.folder_id,
      any_value(c.tender_title) AS tender_title,
      any_value(c.organ_name) AS organ_name,
      any_value(c.detail_url) AS detail_url,
      sort_array(collect_set(c.kind)) AS document_kinds,
      count(*) AS chunks,
      any_value(t.tax_exclusive_amount) AS budget,
      any_value(t.submission_deadline_local) AS submission_deadline
    FROM silver.document_chunks c
    LEFT JOIN silver.tenders t ON c.entry_id = t.entry_id
    GROUP BY c.entry_id, c.folder_id
    ORDER BY c.folder_id
    """
).collect()

catalog = [row.asDict() for row in rows]
print(f"tenders in catalog: {len(catalog)}")

# COMMAND ----------

with open(CATALOG_PATH, "w") as file:
    json.dump(catalog, file, ensure_ascii=False, indent=2)

print(f"written: {CATALOG_PATH}")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT folder_id, tender_title, document_kinds, chunks
# MAGIC FROM (
# MAGIC   SELECT c.folder_id, any_value(c.tender_title) AS tender_title,
# MAGIC          sort_array(collect_set(c.kind)) AS document_kinds, count(*) AS chunks
# MAGIC   FROM silver.document_chunks c
# MAGIC   GROUP BY c.entry_id, c.folder_id
# MAGIC )
# MAGIC ORDER BY chunks DESC
# MAGIC LIMIT 10
