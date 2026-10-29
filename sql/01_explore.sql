-- 01_explore.sql
-- Purpose: profile the raw call center data BEFORE cleaning it.
-- Every finding here should justify a decision made in 02_clean.sql.
-- Source table: call-center-analysis-cb.call_center.`Raw Data`
 
 
-- 1. Column names and data types
--    Shows how BigQuery loaded each column (e.g. whether "Answer Rate" came in as text because of the % sign).
SELECT column_name, data_type
FROM `call-center-analysis-cb.call_center.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'Raw Data'
ORDER BY ordinal_position;
 
 
-- 2. Row count and duplicate check
--    total_rows should equal distinct_ids if Index is a unique key.
SELECT
  COUNT(*)                AS total_rows,
  COUNT(DISTINCT `Index`) AS distinct_ids
FROM `call-center-analysis-cb.call_center.Raw Data`;
 
 
-- 3. Missing values per column
SELECT
  COUNTIF(`Index` IS NULL)                      AS null_index,
  COUNTIF(`Incoming Calls` IS NULL)             AS null_incoming,
  COUNTIF(`Answered Calls` IS NULL)             AS null_answered,
  COUNTIF(`Abandoned Calls` IS NULL)            AS null_abandoned,
  COUNTIF(`Answer Rate` IS NULL)                AS null_answer_rate,
  COUNTIF(`Answer Speed _AVG_` IS NULL)         AS null_answer_speed,
  COUNTIF(`Talk Duration _AVG_` IS NULL)        AS null_talk_duration,
  COUNTIF(`Waiting Time _AVG_` IS NULL)         AS null_waiting_time,
  COUNTIF(`Service Level _20 Seconds_` IS NULL) AS null_service_level
FROM `call-center-analysis-cb.call_center.Raw Data`;
 
 
-- 4. Ranges of the numeric columns (spot outliers and impossible values)
SELECT
  MIN(`Incoming Calls`)  AS min_incoming,  MAX(`Incoming Calls`)  AS max_incoming,  ROUND(AVG(`Incoming Calls`), 1)  AS avg_incoming,
  MIN(`Answered Calls`)  AS min_answered,  MAX(`Answered Calls`)  AS max_answered,  ROUND(AVG(`Answered Calls`), 1)  AS avg_answered,
  MIN(`Abandoned Calls`) AS min_abandoned, MAX(`Abandoned Calls`) AS max_abandoned, ROUND(AVG(`Abandoned Calls`), 1) AS avg_abandoned
FROM `call-center-analysis-cb.call_center.Raw Data`;
 
 
-- 5. Ranges of the time columns
SELECT
  MIN(`Answer Speed _AVG_`)  AS min_answer_speed,  MAX(`Answer Speed _AVG_`)  AS max_answer_speed,
  MIN(`Talk Duration _AVG_`) AS min_talk_duration, MAX(`Talk Duration _AVG_`) AS max_talk_duration,
  MIN(`Waiting Time _AVG_`)  AS min_waiting_time,  MAX(`Waiting Time _AVG_`)  AS max_waiting_time
FROM `call-center-analysis-cb.call_center.Raw Data`;
 
 
-- 6. Logic checks
--    impossible_rows: more calls answered than came in (this is what 02_clean.sql filters out)
--    mismatched_totals: answered + abandoned doesn't add up to incoming
SELECT
  COUNTIF(`Answered Calls` > `Incoming Calls`)                       AS impossible_rows,
  COUNTIF(`Answered Calls` + `Abandoned Calls` != `Incoming Calls`)  AS mismatched_totals
FROM `call-center-analysis-cb.call_center.Raw Data`;
 
 
-- 7. Look at the problem rows themselves
SELECT *
FROM `call-center-analysis-cb.call_center.Raw Data`
WHERE `Answered Calls` > `Incoming Calls`
   OR `Answered Calls` + `Abandoned Calls` != `Incoming Calls`
ORDER BY `Index`
LIMIT 25;