# Databricks notebook source
# MAGIC %md
# MAGIC # 07 - Vector Search index
# MAGIC
# MAGIC Creates the Vector Search endpoint and a Delta Sync index over `silver.document_chunks` with managed multilingual embeddings, or triggers a sync when the index already exists. Waits until every chunk is indexed and ends with a sample query.
# MAGIC
# MAGIC **Reads:** `silver.document_chunks`
# MAGIC
# MAGIC **Writes:** Vector Search endpoint and index `silver.document_chunks_index`

# COMMAND ----------

# MAGIC %pip install databricks-vectorsearch

# COMMAND ----------

import time

from databricks.vector_search.client import VectorSearchClient

dbutils.widgets.text("catalog", "procurement")
dbutils.widgets.text("endpoint_name", "procurement_vs")
dbutils.widgets.text("embedding_endpoint", "databricks-qwen3-embedding-0-6b")
CATALOG = dbutils.widgets.get("catalog")
ENDPOINT_NAME = dbutils.widgets.get("endpoint_name")
EMBEDDING_ENDPOINT = dbutils.widgets.get("embedding_endpoint")

SOURCE_TABLE = f"{CATALOG}.silver.document_chunks"
INDEX_NAME = f"{CATALOG}.silver.document_chunks_index"
SYNCED_COLUMNS = [
    "chunk_id",
    "doc_id",
    "entry_id",
    "folder_id",
    "kind",
    "file_name",
    "tender_title",
    "organ_name",
    "detail_url",
    "page_start",
    "page_end",
    "text",
]

SYNC_TIMEOUT_SECONDS = 3000
SYNC_POLL_SECONDS = 30

client = VectorSearchClient(disable_notice=True)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Endpoint

# COMMAND ----------

endpoint_names = [e["name"] for e in client.list_endpoints().get("endpoints", [])]
print(f"existing endpoints: {endpoint_names}")

if ENDPOINT_NAME not in endpoint_names:
    client.create_endpoint_and_wait(name=ENDPOINT_NAME, endpoint_type="STANDARD")

print(f"endpoint ready: {ENDPOINT_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Index

# COMMAND ----------

index_names = [
    i["name"] for i in client.list_indexes(name=ENDPOINT_NAME).get("vector_indexes", [])
]

if INDEX_NAME not in index_names:
    index = client.create_delta_sync_index_and_wait(
        endpoint_name=ENDPOINT_NAME,
        index_name=INDEX_NAME,
        source_table_name=SOURCE_TABLE,
        primary_key="chunk_id",
        pipeline_type="TRIGGERED",
        embedding_source_column="embed_text",
        embedding_model_endpoint_name=EMBEDDING_ENDPOINT,
        columns_to_sync=SYNCED_COLUMNS,
    )
    print(f"index created: {INDEX_NAME}")
else:
    index = client.get_index(endpoint_name=ENDPOINT_NAME, index_name=INDEX_NAME)
    index.sync()
    print(f"sync triggered: {INDEX_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Wait for the sync

# COMMAND ----------

source_rows = spark.table(SOURCE_TABLE).count()
deadline = time.time() + SYNC_TIMEOUT_SECONDS

while True:
    indexed_rows = index.describe().get("status", {}).get("indexed_row_count", 0)
    print(f"indexed rows: {indexed_rows} / {source_rows}")
    if indexed_rows >= source_rows:
        break
    if time.time() > deadline:
        raise TimeoutError(f"index not in sync after {SYNC_TIMEOUT_SECONDS} seconds")
    time.sleep(SYNC_POLL_SECONDS)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sample query

# COMMAND ----------

results = index.similarity_search(
    query_text="plazo de ejecución del contrato y posibilidad de prórroga",
    columns=["folder_id", "kind", "file_name", "page_start", "page_end", "text"],
    num_results=5,
    query_type="HYBRID",
)

for folder_id, kind, file_name, page_start, page_end, text, score in results["result"]["data_array"]:
    print(f"{score:.4f} | {folder_id} | {kind} | {file_name} | p.{page_start}-{page_end}")
    print(f"    {text[:200]}")
