# Databricks notebook source
# MAGIC %md
# MAGIC # 01 - Bronze ingestion
# MAGIC
# MAGIC Downloads the first page of the PLACSP tender Atom feed and appends each `<entry>` as raw XML to `procurement.bronze.tenders_raw`.

# COMMAND ----------

import requests
import xml.etree.ElementTree as ET
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

FEED_URL = "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
ATOM = "http://www.w3.org/2005/Atom"
TABLE = "procurement.bronze.tenders_raw"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Download the feed page

# COMMAND ----------

response = requests.get(FEED_URL, timeout=120)
response.raise_for_status()
print(response.status_code, len(response.content))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Register XML namespace prefixes

# COMMAND ----------

NAMESPACES = {
    "": ATOM,
    "cbc": "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2",
    "cbc-place-ext": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2",
    "cac-place-ext": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2",
    "at": "http://purl.org/atompub/tombstones/1.0",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}

for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Extract entries

# COMMAND ----------

root = ET.fromstring(response.content)
entries = root.findall(f"{{{ATOM}}}entry")
print(f"entries found: {len(entries)}")

rows = []
for entry in entries:
    entry_id = entry.find(f"{{{ATOM}}}id").text
    updated = entry.find(f"{{{ATOM}}}updated").text
    raw_xml = ET.tostring(entry, encoding="unicode")
    rows.append((entry_id, updated, raw_xml, FEED_URL))

print(rows[0][0], rows[0][1])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Bronze

# COMMAND ----------

schema = StructType([
    StructField("entry_id", StringType(), False),
    StructField("updated", StringType(), False),
    StructField("raw_xml", StringType(), False),
    StructField("source_url", StringType(), False),
])

df = spark.createDataFrame(rows, schema).withColumn("ingested_at", F.current_timestamp())
df.write.mode("append").saveAsTable(TABLE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) AS row_count FROM procurement.bronze.tenders_raw

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT entry_id, updated, length(raw_xml) AS bytes
# MAGIC FROM procurement.bronze.tenders_raw
# MAGIC ORDER BY updated DESC
# MAGIC LIMIT 5

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT substring(raw_xml, 1, 400) AS raw_xml_preview
# MAGIC FROM procurement.bronze.tenders_raw
# MAGIC LIMIT 1
