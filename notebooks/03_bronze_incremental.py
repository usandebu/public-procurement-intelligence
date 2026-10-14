# Databricks notebook source
# MAGIC %md
# MAGIC # 03 - Bronze incremental ingestion
# MAGIC
# MAGIC Walks the PLACSP Atom feed backwards from the newest page until it reaches the stored watermark, and merges in-scope tenders (CPV prefix) and tombstones into Bronze.

# COMMAND ----------

import os
import sys
from datetime import UTC, datetime, timedelta

from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType, TimestampType

sys.path.append(os.path.abspath("../src"))

from procurement.feed import collect_since

FEED_URL = "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
CPV_PREFIX = "72"
BACKFILL_DAYS = 7
MAX_PAGES = None

TENDERS_TABLE = "procurement.bronze.tenders_raw"
TOMBSTONES_TABLE = "procurement.bronze.tenders_tombstones_raw"
RUNS_TABLE = "procurement.bronze.ingestion_runs"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tables

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS procurement.bronze.tenders_raw (
# MAGIC   entry_id STRING,
# MAGIC   updated STRING,
# MAGIC   updated_ts TIMESTAMP,
# MAGIC   raw_xml STRING,
# MAGIC   source_url STRING,
# MAGIC   ingested_at TIMESTAMP
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS procurement.bronze.tenders_tombstones_raw (
# MAGIC   ref STRING,
# MAGIC   `when` STRING,
# MAGIC   when_ts TIMESTAMP,
# MAGIC   comment_type STRING,
# MAGIC   source_url STRING,
# MAGIC   ingested_at TIMESTAMP
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS procurement.bronze.ingestion_runs (
# MAGIC   run_at TIMESTAMP,
# MAGIC   watermark_from TIMESTAMP,
# MAGIC   max_seen_updated TIMESTAMP,
# MAGIC   pages INT,
# MAGIC   entries_seen INT,
# MAGIC   entries_kept INT,
# MAGIC   tombstones_kept INT
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %md
# MAGIC ## Watermark

# COMMAND ----------

last_ms = spark.sql(
    f"SELECT max(unix_millis(max_seen_updated)) AS ms FROM {RUNS_TABLE}"
).first()["ms"]

if last_ms is not None:
    watermark = datetime.fromtimestamp(last_ms / 1000, tz=UTC)
else:
    watermark = datetime.now(UTC) - timedelta(days=BACKFILL_DAYS)

print(f"watermark: {watermark.isoformat()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Merge helpers

# COMMAND ----------

tender_schema = StructType(
    [
        StructField("entry_id", StringType(), False),
        StructField("updated", StringType(), False),
        StructField("updated_ts", TimestampType(), False),
        StructField("raw_xml", StringType(), False),
        StructField("source_url", StringType(), False),
    ]
)

tombstone_schema = StructType(
    [
        StructField("ref", StringType(), False),
        StructField("when", StringType(), False),
        StructField("when_ts", TimestampType(), False),
        StructField("comment_type", StringType(), True),
        StructField("source_url", StringType(), False),
    ]
)


def merge_tenders(rows):
    df = spark.createDataFrame(rows, tender_schema).withColumn(
        "ingested_at", F.current_timestamp()
    )
    df.createOrReplaceTempView("tenders_batch")
    spark.sql(
        f"""
        MERGE INTO {TENDERS_TABLE} t
        USING tenders_batch s
        ON t.entry_id = s.entry_id AND t.updated = s.updated
        WHEN NOT MATCHED THEN INSERT *
        """
    )


def merge_tombstones(rows):
    df = spark.createDataFrame(rows, tombstone_schema).withColumn(
        "ingested_at", F.current_timestamp()
    )
    df.createOrReplaceTempView("tombstones_batch")
    spark.sql(
        f"""
        MERGE INTO {TOMBSTONES_TABLE} t
        USING tombstones_batch s
        ON t.ref = s.ref AND t.`when` = s.`when`
        WHEN NOT MATCHED THEN INSERT *
        """
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Ingest

# COMMAND ----------

run_at = datetime.now(UTC)
pages_read = 0
entries_seen = 0
entries_kept = 0
tombstones_kept = 0
max_seen = watermark

for page in collect_since(FEED_URL, watermark, CPV_PREFIX, max_pages=MAX_PAGES):
    pages_read += 1
    entries_seen += len(page.entries)
    if page.max_updated is not None:
        max_seen = max(max_seen, page.max_updated)

    tender_rows = [
        (e.entry_id, e.updated, e.updated_ts, e.raw_xml, FEED_URL)
        for e in page.new_entries(watermark)
    ]
    tombstone_rows = [
        (t.ref, t.when, t.when_ts, t.comment_type, FEED_URL)
        for t in page.new_tombstones(watermark)
    ]

    if tender_rows:
        merge_tenders(tender_rows)
    if tombstone_rows:
        merge_tombstones(tombstone_rows)

    entries_kept += len(tender_rows)
    tombstones_kept += len(tombstone_rows)
    print(
        f"page {pages_read}: seen={len(page.entries)} kept={len(tender_rows)} "
        f"tombstones={len(tombstone_rows)} oldest={page.min_updated}"
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Record the run

# COMMAND ----------

spark.createDataFrame(
    [(run_at, watermark, max_seen, pages_read, entries_seen, entries_kept, tombstones_kept)],
    "run_at timestamp, watermark_from timestamp, max_seen_updated timestamp, "
    "pages int, entries_seen int, entries_kept int, tombstones_kept int",
).write.mode("append").saveAsTable(RUNS_TABLE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM procurement.bronze.ingestion_runs ORDER BY run_at DESC

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) AS tenders, count(DISTINCT entry_id) AS distinct_tenders, min(updated_ts) AS oldest, max(updated_ts) AS newest
# MAGIC FROM procurement.bronze.tenders_raw

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT comment_type, count(*) AS tombstones FROM procurement.bronze.tenders_tombstones_raw GROUP BY comment_type
