-- 02_clean.sql
-- Purpose: build clean_data from Raw Data.
-- Fixes: snake_case names, TIME fields -> whole seconds.
-- Rows: the WHERE filters are a safety net. 01_explore.sql found 0 bad rows, so none are dropped.
-- Rows with NULL Answered Calls or Incoming Calls are dropped on purpose, because they can't be reconciled (answered + abandoned = incoming). 03_validate.sql check 1 is the ongoing proof of how many rows this drops.
-- Abandoned Calls and the time columns have no NULL filter here; 03_validate.sql check 5 counts NULLs in every column, so any NULL there gets flagged.
CREATE OR REPLACE TABLE `call-center-analysis-cb.call_center.clean_data` AS
SELECT
  `Index` AS row_id,
  `Incoming Calls` AS incoming_calls,
  `Answered Calls` AS answered_calls,
  `Abandoned Calls` AS abandoned_calls,
  `Answer Rate` AS answer_rate,
  TIME_DIFF(`Answer Speed _AVG_`, TIME '00:00:00', SECOND) AS avg_answer_speed_sec,
  TIME_DIFF(`Talk Duration _AVG_`, TIME '00:00:00', SECOND) AS avg_talk_duration_sec,
  TIME_DIFF(`Waiting Time _AVG_`, TIME '00:00:00', SECOND) AS avg_waiting_time_sec,
  `Service Level _20 Seconds_` AS service_level_20s
FROM `call-center-analysis-cb.call_center.Raw Data`
WHERE `Index` IS NOT NULL
  AND `Answered Calls` IS NOT NULL
  AND `Incoming Calls` IS NOT NULL
  AND `Answered Calls` <= `Incoming Calls`;   -- drop NULL and impossible rows
