# Databricks notebook source
# MAGIC %md
# MAGIC # 08 - Evaluate retrieval
# MAGIC
# MAGIC Samples chunks, asks an LLM to write one question answerable from each chunk, and measures whether the Vector Search index returns the source chunk (hit@k and MRR). Each run is appended to `gold.rag_eval_results` so retrieval configurations can be compared.
# MAGIC
# MAGIC **Reads:** `silver.document_chunks`, Vector Search index `silver.document_chunks_index`
# MAGIC
# MAGIC **Writes:** `gold.rag_eval_questions`, `gold.rag_eval_results`

# COMMAND ----------

# MAGIC %pip install databricks-vectorsearch

# COMMAND ----------

import contextlib
import io
import os
import sys
import uuid
from datetime import UTC, datetime

from databricks.vector_search.client import VectorSearchClient

sys.path.append(os.path.abspath("../src"))

from procurement.evaluation import (
    first_rank,
    first_rank_by_location,
    hit_rate,
    mean_reciprocal_rank,
)

dbutils.widgets.text("catalog", "procurement")
dbutils.widgets.text("endpoint_name", "procurement_vs")
dbutils.widgets.text("n_questions", "100")
dbutils.widgets.text("query_type", "HYBRID")
dbutils.widgets.text("top_k", "10")
dbutils.widgets.text("scope_to_tender", "false")
dbutils.widgets.text("generator_endpoint", "databricks-gpt-oss-120b")
CATALOG = dbutils.widgets.get("catalog")
ENDPOINT_NAME = dbutils.widgets.get("endpoint_name")
N_QUESTIONS = int(dbutils.widgets.get("n_questions"))
QUERY_TYPE = dbutils.widgets.get("query_type")
TOP_K = int(dbutils.widgets.get("top_k"))
SCOPE_TO_TENDER = dbutils.widgets.get("scope_to_tender").lower() == "true"
GENERATOR = dbutils.widgets.get("generator_endpoint")

spark.sql(f"USE CATALOG {CATALOG}")
INDEX_NAME = f"{CATALOG}.silver.document_chunks_index"
MIN_CHUNK_CHARS = 600

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tables

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS gold

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS gold.rag_eval_questions (
# MAGIC   question_id STRING,
# MAGIC   chunk_id STRING,
# MAGIC   doc_id STRING,
# MAGIC   folder_id STRING,
# MAGIC   kind STRING,
# MAGIC   page_start INT,
# MAGIC   page_end INT,
# MAGIC   question STRING,
# MAGIC   generated_at TIMESTAMP
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS gold.rag_eval_results (
# MAGIC   run_id STRING,
# MAGIC   run_at TIMESTAMP,
# MAGIC   index_name STRING,
# MAGIC   query_type STRING,
# MAGIC   top_k INT,
# MAGIC   scoped BOOLEAN,
# MAGIC   question_id STRING,
# MAGIC   chunk_rank INT,
# MAGIC   location_rank INT
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate questions

# COMMAND ----------

existing = spark.table("gold.rag_eval_questions").count()
print(f"existing questions: {existing}")

if existing < N_QUESTIONS:
    spark.sql(
        f"""
        INSERT INTO gold.rag_eval_questions
        SELECT
          uuid() AS question_id,
          chunk_id, doc_id, folder_id, kind, page_start, page_end,
          trim(ai_query(
            '{GENERATOR}',
            concat(
              'Eres un licitador que estudia un pliego de contratación pública. ',
              'Escribe UNA pregunta en español, autocontenida, que se pueda responder únicamente con el fragmento siguiente. ',
              'No menciones "el fragmento" ni "el texto". Responde solo con la pregunta.\n\nFragmento:\n',
              text
            )
          )) AS question,
          current_timestamp() AS generated_at
        FROM (
          SELECT * FROM silver.document_chunks
          WHERE char_count >= {MIN_CHUNK_CHARS}
            AND chunk_id NOT IN (SELECT chunk_id FROM gold.rag_eval_questions)
          ORDER BY rand(42)
          LIMIT {N_QUESTIONS - existing}
        )
        """
    )

questions = spark.sql(
    """
    SELECT q.*, c.entry_id
    FROM gold.rag_eval_questions q
    JOIN silver.document_chunks c ON q.chunk_id = c.chunk_id
    """
).collect()
print(f"questions available: {len(questions)}")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT folder_id, kind, question FROM gold.rag_eval_questions LIMIT 10

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run retrieval

# COMMAND ----------

client = VectorSearchClient(disable_notice=True)
index = client.get_index(endpoint_name=ENDPOINT_NAME, index_name=INDEX_NAME)

run_id = str(uuid.uuid4())
run_at = datetime.now(UTC)
result_rows = []
failures = 0

for q in questions:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            response = index.similarity_search(
                query_text=q.question,
                columns=["chunk_id", "doc_id", "page_start", "page_end"],
                num_results=TOP_K,
                query_type=QUERY_TYPE,
                filters={"entry_id": q.entry_id} if SCOPE_TO_TENDER else None,
            )
        found = response["result"]["data_array"]
    except Exception as error:
        failures += 1
        print(f"query failed: {str(error)[:120]}")
        continue

    chunk_ids = [row[0] for row in found]
    locations = [(row[1], int(row[2]), int(row[3])) for row in found]
    result_rows.append(
        (
            run_id,
            run_at,
            INDEX_NAME,
            QUERY_TYPE,
            TOP_K,
            SCOPE_TO_TENDER,
            q.question_id,
            first_rank(q.chunk_id, chunk_ids),
            first_rank_by_location(q.doc_id, q.page_start, q.page_end, locations),
        )
    )

print(f"evaluated: {len(result_rows)} | failed: {failures}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save and summarise

# COMMAND ----------

if result_rows:
    spark.createDataFrame(
        result_rows,
        "run_id string, run_at timestamp, index_name string, query_type string, top_k int, "
        "scoped boolean, question_id string, chunk_rank int, location_rank int",
    ).write.mode("append").option("mergeSchema", "true").saveAsTable("gold.rag_eval_results")

chunk_ranks = [row[7] for row in result_rows]
location_ranks = [row[8] for row in result_rows]

print(f"query_type={QUERY_TYPE} scoped_to_tender={SCOPE_TO_TENDER} questions={len(result_rows)}")
for k in (1, 3, 5, 10):
    if k <= TOP_K:
        print(
            f"hit@{k:<2d} chunk={hit_rate(chunk_ranks, k):.3f}  "
            f"document+page={hit_rate(location_ranks, k):.3f}"
        )
print(f"MRR   chunk={mean_reciprocal_rank(chunk_ranks):.3f}  document+page={mean_reciprocal_rank(location_ranks):.3f}")

# COMMAND ----------

# MAGIC %sql
# MAGIC WITH runs AS (
# MAGIC   SELECT run_id, query_type, coalesce(scoped, false) AS scoped_to_tender, count(*) AS questions,
# MAGIC          round(avg(CASE WHEN chunk_rank <= 5 THEN 1 ELSE 0 END), 3) AS hit_at_5_chunk,
# MAGIC          round(avg(CASE WHEN location_rank <= 5 THEN 1 ELSE 0 END), 3) AS hit_at_5_location,
# MAGIC          max(run_at) AS run_at
# MAGIC   FROM gold.rag_eval_results
# MAGIC   GROUP BY run_id, query_type, coalesce(scoped, false)
# MAGIC )
# MAGIC SELECT query_type, scoped_to_tender, questions, hit_at_5_chunk, hit_at_5_location, run_at
# MAGIC FROM runs
# MAGIC QUALIFY row_number() OVER (PARTITION BY query_type, scoped_to_tender ORDER BY run_at DESC) = 1
# MAGIC ORDER BY scoped_to_tender, query_type
