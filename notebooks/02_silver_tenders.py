# Databricks notebook source
# MAGIC %md
# MAGIC # 02 - Silver tenders
# MAGIC
# MAGIC Rebuilds the Silver layer from Bronze: latest version per tender, annulled tenders removed, CODICE XML parsed into typed columns, and rows failing quality rules routed to a rejects table.
# MAGIC
# MAGIC **Reads:** `procurement.bronze.tenders_raw`, `procurement.bronze.tenders_tombstones_raw`
# MAGIC
# MAGIC **Writes:** `procurement.silver.tenders`, `procurement.silver.tender_awarding_criteria`, `procurement.silver.tender_documents`, `procurement.silver.tenders_rejected`

# COMMAND ----------

import os
import sys

from pyspark.sql import Window
from pyspark.sql import functions as F

sys.path.append(os.path.abspath("../src"))

from procurement.silver import safe_parse_tender

BRONZE_TENDERS = "procurement.bronze.tenders_raw"
BRONZE_TOMBSTONES = "procurement.bronze.tenders_tombstones_raw"

SILVER_TENDERS = "procurement.silver.tenders"
SILVER_CRITERIA = "procurement.silver.tender_awarding_criteria"
SILVER_DOCUMENTS = "procurement.silver.tender_documents"
SILVER_REJECTED = "procurement.silver.tenders_rejected"

# Struct returned by safe_parse_tender for one raw_xml
PARSED_SCHEMA = """
    folder_id string,
    title string,
    status_code string,
    detail_url string,
    organ_name string,
    organ_nif string,
    organ_city string,
    parent_organ_name string,
    contract_type_code string,
    contract_subtype_code string,
    estimated_amount double,
    total_amount double,
    tax_exclusive_amount double,
    currency string,
    cpv_codes array<string>,
    nuts_code string,
    province string,
    procedure_code string,
    urgency_code string,
    submission_deadline_local string,
    criteria array<struct<
        position: int,
        lot_id: string,
        type_code: string,
        subtype_code: string,
        description: string,
        weight: double,
        note: string
    >>,
    documents array<struct<
        kind: string,
        file_name: string,
        uri: string,
        document_hash: string,
        type_code: string
    >>,
    quality_errors array<string>
"""

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS procurement.silver

# COMMAND ----------

# MAGIC %md
# MAGIC ## Latest version per tender, annulled tenders removed

# COMMAND ----------

bronze = spark.table(BRONZE_TENDERS)

latest = (
    bronze.withColumn(
        "version_rank",
        F.row_number().over(
            Window.partitionBy("entry_id").orderBy(F.col("updated_ts").desc())
        ),
    )
    .filter("version_rank = 1")
    .drop("version_rank")
)

annulled = (
    latest.join(
        spark.table(BRONZE_TOMBSTONES).select(
            F.col("ref").alias("entry_id"), "when_ts"
        ),
        "entry_id",
    )
    .filter(F.col("when_ts") >= F.col("updated_ts"))
    .select("entry_id")
    .distinct()
)

alive = latest.join(annulled, "entry_id", "left_anti")

print(f"bronze rows:        {bronze.count()}")
print(f"latest versions:    {latest.count()}")
print(f"annulled:           {annulled.count()}")
print(f"alive:              {alive.count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parse CODICE XML

# COMMAND ----------

parse_tender_udf = F.udf(lambda raw_xml: safe_parse_tender(raw_xml), PARSED_SCHEMA)

parsed = alive.select(
    "entry_id",
    F.col("updated_ts").alias("version_ts"),
    "raw_xml",
    parse_tender_udf("raw_xml").alias("parsed"),
)

valid = parsed.filter(F.size("parsed.quality_errors") == 0)
rejected = parsed.filter(F.size("parsed.quality_errors") > 0)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build Silver tables

# COMMAND ----------

tenders = valid.select("entry_id", "version_ts", "parsed.*").drop(
    "criteria", "documents", "quality_errors"
)

criteria = (
    valid.select("entry_id", "parsed.folder_id", F.explode("parsed.criteria").alias("c"))
    .select("entry_id", "folder_id", "c.*")
)

documents = (
    valid.select("entry_id", "parsed.folder_id", F.explode("parsed.documents").alias("d"))
    .select("entry_id", "folder_id", "d.*")
)

rejects = rejected.select(
    "entry_id", "version_ts", "raw_xml", F.col("parsed.quality_errors").alias("errors")
)

for name, df in [
    (SILVER_TENDERS, tenders),
    (SILVER_CRITERIA, criteria),
    (SILVER_DOCUMENTS, documents),
    (SILVER_REJECTED, rejects),
]:
    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(name)
    print(f"{name}: {spark.table(name).count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quality checks

# COMMAND ----------

tender_rows = spark.table(SILVER_TENDERS).count()
distinct_entries = spark.table(SILVER_TENDERS).select("entry_id").distinct().count()
assert tender_rows == distinct_entries, "Silver tenders must hold one row per entry_id"
print("one row per tender: OK")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT status_code, count(*) AS tenders
# MAGIC FROM procurement.silver.tenders
# MAGIC GROUP BY status_code
# MAGIC ORDER BY tenders DESC

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT folder_id, title, organ_name, total_amount, submission_deadline_local, cpv_codes
# MAGIC FROM procurement.silver.tenders
# MAGIC ORDER BY version_ts DESC
# MAGIC LIMIT 10

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT kind, count(*) AS documents
# MAGIC FROM procurement.silver.tender_documents
# MAGIC GROUP BY kind
# MAGIC ORDER BY documents DESC

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT errors, count(*) AS rejected
# MAGIC FROM procurement.silver.tenders_rejected
# MAGIC GROUP BY errors
