# Databricks notebook source
# MAGIC %md
# MAGIC # 03 - Gold tenders
# MAGIC
# MAGIC Analytical tables over Silver for the dashboard and Genie: open tenders, spend by organ, budget bands and award-criteria weights.
# MAGIC
# MAGIC **Reads:** `procurement.silver.tenders`, `procurement.silver.tender_awarding_criteria`
# MAGIC
# MAGIC **Writes:** `procurement.gold.open_tenders`, `procurement.gold.organ_summary`, `procurement.gold.budget_bands`, `procurement.gold.tender_criteria_weights`

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS procurement.gold

# COMMAND ----------

# MAGIC %md
# MAGIC ## Criteria weights per tender

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE procurement.gold.tender_criteria_weights AS
# MAGIC SELECT
# MAGIC   entry_id,
# MAGIC   folder_id,
# MAGIC   count(*) AS criteria_count,
# MAGIC   sum(weight) AS total_weight,
# MAGIC   sum(CASE WHEN type_code = 'OBJ' THEN weight ELSE 0 END) AS objective_weight,
# MAGIC   sum(CASE WHEN type_code = 'SUBJ' THEN weight ELSE 0 END) AS subjective_weight
# MAGIC FROM procurement.silver.tender_awarding_criteria
# MAGIC GROUP BY entry_id, folder_id

# COMMAND ----------

# MAGIC %md
# MAGIC ## Open tenders

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE procurement.gold.open_tenders AS
# MAGIC SELECT
# MAGIC   t.entry_id,
# MAGIC   t.folder_id,
# MAGIC   t.title,
# MAGIC   t.organ_name,
# MAGIC   t.parent_organ_name,
# MAGIC   t.province,
# MAGIC   t.tax_exclusive_amount,
# MAGIC   t.total_amount,
# MAGIC   t.estimated_amount,
# MAGIC   to_timestamp(t.submission_deadline_local) AS submission_deadline,
# MAGIC   datediff(to_date(t.submission_deadline_local), to_date(from_utc_timestamp(current_timestamp(), 'Europe/Madrid'))) AS days_to_deadline,
# MAGIC   w.subjective_weight,
# MAGIC   t.cpv_codes,
# MAGIC   t.detail_url
# MAGIC FROM procurement.silver.tenders t
# MAGIC LEFT JOIN procurement.gold.tender_criteria_weights w ON t.entry_id = w.entry_id
# MAGIC WHERE t.status_code = 'PUB'
# MAGIC   AND to_timestamp(t.submission_deadline_local) >= from_utc_timestamp(current_timestamp(), 'Europe/Madrid')

# COMMAND ----------

# MAGIC %md
# MAGIC ## Spend by organ

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE procurement.gold.organ_summary AS
# MAGIC SELECT
# MAGIC   organ_nif,
# MAGIC   organ_name,
# MAGIC   parent_organ_name,
# MAGIC   count(*) AS tenders,
# MAGIC   count_if(status_code = 'PUB') AS published_tenders,
# MAGIC   sum(tax_exclusive_amount) AS total_budget,
# MAGIC   avg(tax_exclusive_amount) AS avg_budget
# MAGIC FROM procurement.silver.tenders
# MAGIC GROUP BY organ_nif, organ_name, parent_organ_name

# COMMAND ----------

# MAGIC %md
# MAGIC ## Budget bands

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE procurement.gold.budget_bands AS
# MAGIC SELECT
# MAGIC   CASE
# MAGIC     WHEN tax_exclusive_amount IS NULL THEN 6
# MAGIC     WHEN tax_exclusive_amount < 15000 THEN 1
# MAGIC     WHEN tax_exclusive_amount < 50000 THEN 2
# MAGIC     WHEN tax_exclusive_amount < 100000 THEN 3
# MAGIC     WHEN tax_exclusive_amount < 500000 THEN 4
# MAGIC     ELSE 5
# MAGIC   END AS band_order,
# MAGIC   CASE
# MAGIC     WHEN tax_exclusive_amount IS NULL THEN 'unknown'
# MAGIC     WHEN tax_exclusive_amount < 15000 THEN '< 15k'
# MAGIC     WHEN tax_exclusive_amount < 50000 THEN '15k - 50k'
# MAGIC     WHEN tax_exclusive_amount < 100000 THEN '50k - 100k'
# MAGIC     WHEN tax_exclusive_amount < 500000 THEN '100k - 500k'
# MAGIC     ELSE '>= 500k'
# MAGIC   END AS band,
# MAGIC   count(*) AS tenders,
# MAGIC   sum(tax_exclusive_amount) AS total_budget
# MAGIC FROM procurement.silver.tenders
# MAGIC GROUP BY 1, 2

# COMMAND ----------

# MAGIC %md
# MAGIC ## Checks

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 'tenders' AS metric, count(*) AS value FROM procurement.silver.tenders
# MAGIC UNION ALL SELECT 'open_tenders', count(*) FROM procurement.gold.open_tenders
# MAGIC UNION ALL SELECT 'organs', count(*) FROM procurement.gold.organ_summary
# MAGIC UNION ALL SELECT 'tenders_with_criteria', count(*) FROM procurement.gold.tender_criteria_weights
# MAGIC UNION ALL SELECT 'tenders_without_budget', count(*) FROM procurement.silver.tenders WHERE tax_exclusive_amount IS NULL

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM procurement.gold.budget_bands ORDER BY band_order

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT folder_id, title, organ_name, tax_exclusive_amount, days_to_deadline, subjective_weight
# MAGIC FROM procurement.gold.open_tenders
# MAGIC ORDER BY days_to_deadline
# MAGIC LIMIT 10

# COMMAND ----------

# MAGIC %md
# MAGIC ## Award-criteria codes to verify before building a price-weight metric

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT type_code, subtype_code, count(*) AS criteria, min(description) AS example_description
# MAGIC FROM procurement.silver.tender_awarding_criteria
# MAGIC GROUP BY type_code, subtype_code
# MAGIC ORDER BY criteria DESC
