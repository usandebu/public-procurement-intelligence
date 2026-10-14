# Databricks notebook source
# MAGIC %md
# MAGIC # 02 - Explore feed pagination
# MAGIC
# MAGIC Follows the `rel="next"` chain from the first feed page and prints, for each page, the number of entries and the range of `updated` timestamps.

# COMMAND ----------

import requests
import xml.etree.ElementTree as ET

FEED_URL = "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
ATOM = "http://www.w3.org/2005/Atom"
MAX_PAGES = 8

# COMMAND ----------

def fetch_page(url):
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    entries = root.findall(f"{{{ATOM}}}entry")
    updated = [e.find(f"{{{ATOM}}}updated").text for e in entries]
    next_url = None
    for link in root.findall(f"{{{ATOM}}}link"):
        if link.get("rel") == "next":
            next_url = link.get("href")
    deleted = root.findall("{http://purl.org/atompub/tombstones/1.0}deleted-entry")
    return {
        "url": url,
        "bytes": len(response.content),
        "entries": len(entries),
        "deleted": len(deleted),
        "min_updated": min(updated) if updated else None,
        "max_updated": max(updated) if updated else None,
        "next_url": next_url,
    }

# COMMAND ----------

pages = []
url = FEED_URL
for _ in range(MAX_PAGES):
    if url is None:
        break
    page = fetch_page(url)
    pages.append(page)
    print(page["entries"], page["deleted"], page["min_updated"], page["max_updated"], page["url"].rsplit("/", 1)[-1])
    url = page["next_url"]

# COMMAND ----------

display(spark.createDataFrame(pages))
