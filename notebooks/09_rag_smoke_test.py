# Databricks notebook source
# MAGIC %md
# MAGIC # 09 - RAG smoke test
# MAGIC
# MAGIC Answers sample questions end to end: hybrid retrieval scoped to a tender, generation with the LLM from the retrieved fragments only, and cited sources. Includes two unanswerable questions (an unrelated one and a question from another tender) to check the refusal.
# MAGIC
# MAGIC **Reads:** Vector Search index `silver.document_chunks_index`, `gold.rag_eval_questions`, `silver.document_chunks`
# MAGIC
# MAGIC **Writes:** nothing

# COMMAND ----------

# MAGIC %pip install databricks-vectorsearch openai

# COMMAND ----------

import contextlib
import io
import os
import sys

from databricks.sdk import WorkspaceClient
from databricks.vector_search.client import VectorSearchClient

sys.path.append(os.path.abspath("../src"))

from procurement.rag import (
    SEARCH_COLUMNS,
    build_messages,
    cited_sources,
    extract_text,
    is_no_answer,
    normalize_citations,
    parse_sources,
)

dbutils.widgets.text("catalog", "procurement")
dbutils.widgets.text("endpoint_name", "procurement_vs")
dbutils.widgets.text("generator_endpoint", "databricks-gpt-oss-120b")
dbutils.widgets.text("n_samples", "6")
CATALOG = dbutils.widgets.get("catalog")
ENDPOINT_NAME = dbutils.widgets.get("endpoint_name")
GENERATOR = dbutils.widgets.get("generator_endpoint")
N_SAMPLES = int(dbutils.widgets.get("n_samples"))

spark.sql(f"USE CATALOG {CATALOG}")
INDEX_NAME = f"{CATALOG}.silver.document_chunks_index"
NUM_RESULTS = 5

index = VectorSearchClient(disable_notice=True).get_index(
    endpoint_name=ENDPOINT_NAME, index_name=INDEX_NAME
)
llm = WorkspaceClient().serving_endpoints.get_open_ai_client()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Answer function

# COMMAND ----------

def answer(question, entry_id=None):
    with contextlib.redirect_stdout(io.StringIO()):
        response = index.similarity_search(
            query_text=question,
            columns=SEARCH_COLUMNS,
            num_results=NUM_RESULTS,
            query_type="HYBRID",
            filters={"entry_id": entry_id} if entry_id else None,
        )
    sources = parse_sources(response["result"]["data_array"])
    completion = llm.chat.completions.create(
        model=GENERATOR,
        messages=build_messages(question, sources),
        max_tokens=1500,
        temperature=0,
    )
    text = normalize_citations(extract_text(completion.choices[0].message.content))
    return {"answer": text, "sources": sources, "cited": cited_sources(text, sources)}


def show(question, result):
    print(f"Q: {question}")
    print(f"A: {result['answer']}")
    for source in result["cited"]:
        print(f"   [{source.number}] {source.label}")
    print()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sample questions scoped to their tender

# COMMAND ----------

samples = spark.sql(
    f"""
    SELECT q.question, c.entry_id
    FROM gold.rag_eval_questions q
    JOIN silver.document_chunks c ON q.chunk_id = c.chunk_id
    ORDER BY rand(7)
    LIMIT {N_SAMPLES}
    """
).collect()

results = []
for row in samples:
    result = answer(row.question, row.entry_id)
    results.append(result)
    show(row.question, result)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Unanswerable questions

# COMMAND ----------

entry_id = samples[0].entry_id
question = "¿Cuál es el color corporativo del logotipo del adjudicatario?"
result = answer(question, entry_id)
show(question, result)
results.append(result)

question = samples[1].question
result = answer(question, entry_id)
show(f"(question from another tender) {question}", result)
results.append(result)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

with_citations = sum(1 for r in results if r["cited"])
refusals = sum(1 for r in results if is_no_answer(r["answer"]))
print(f"answers: {len(results)}")
print(f"with at least one citation: {with_citations}")
print(f"refusals: {refusals}")
