-- 03_validate.sql
-- Purpose: prove clean_data is right before it goes into Power BI.
-- Every check below should come back as expected (noted on each one).
-- Tables: call-center-analysis-cb.call_center.`Raw Data` (raw) vs clean_data (clean)


-- 1. Row count: raw vs clean
--    Expected: rows_dropped = 0 (02_clean.sql filters are a safety net, nothing should be lost)
SELECT
  (SELECT COUNT(*) FROM `call-center-analysis-cb.call_center.Raw Data`)  AS raw_rows,
  (SELECT COUNT(*) FROM `call-center-analysis-cb.call_center.clean_data`) AS clean_rows,
  (SELECT COUNT(*) FROM `call-center-analysis-cb.call_center.Raw Data`)
    - (SELECT COUNT(*) FROM `call-center-analysis-cb.call_center.clean_data`) AS rows_dropped;


-- 2. Totals reconcile: raw vs clean
--    Expected: every pair matches, so no calls were lost or changed during cleaning
SELECT
  r.incoming  AS raw_incoming,  c.incoming  AS clean_incoming,
  r.answered  AS raw_answered,  c.answered  AS clean_answered,
  r.abandoned AS raw_abandoned, c.abandoned AS clean_abandoned
FROM (
  SELECT SUM(`Incoming Calls`) AS incoming, SUM(`Answered Calls`) AS answered, SUM(`Abandoned Calls`) AS abandoned
  FROM `call-center-analysis-cb.call_center.Raw Data`
) AS r
CROSS JOIN (
  SELECT SUM(incoming_calls) AS incoming, SUM(answered_calls) AS answered, SUM(abandoned_calls) AS abandoned
  FROM `call-center-analysis-cb.call_center.clean_data`
) AS c;


-- 3. Business logic: answered + abandoned = incoming, in every row
--    Expected: 0
SELECT COUNTIF(answered_calls + abandoned_calls != incoming_calls) AS mismatched_rows
FROM `call-center-analysis-cb.call_center.clean_data`;


-- 4. Answer rate matches answered / incoming
--    answer_rate is stored as a decimal (0.553 = 55.3%), so compare it to the ratio directly.
--    Tolerance of 0.001 covers the source rounding to 2 decimal places of a percent.
--    Expected: 0
SELECT COUNTIF(ABS(answer_rate - SAFE_DIVIDE(answered_calls, incoming_calls)) > 0.001) AS off_rate_rows
FROM `call-center-analysis-cb.call_center.clean_data`;


-- 5. Keys and nulls
--    Expected: all zeros, and total_rows = distinct_ids
SELECT
  COUNT(*)               AS total_rows,
  COUNT(DISTINCT row_id) AS distinct_ids,
  COUNTIF(row_id IS NULL
       OR incoming_calls IS NULL
       OR answered_calls IS NULL
       OR abandoned_calls IS NULL
       OR answer_rate IS NULL
       OR avg_answer_speed_sec IS NULL
       OR avg_talk_duration_sec IS NULL
       OR avg_waiting_time_sec IS NULL
       OR service_level_20s IS NULL) AS rows_with_nulls
FROM `call-center-analysis-cb.call_center.clean_data`;


-- 6. Time conversion check (TIME -> seconds)
--    Row 1 in the raw file: answer speed 0:00:17, talk 0:02:14, waiting 0:02:45
--    Expected: 17, 134, 165
SELECT row_id, avg_answer_speed_sec, avg_talk_duration_sec, avg_waiting_time_sec
FROM `call-center-analysis-cb.call_center.clean_data`
WHERE row_id = 1;


-- 7. Ranges look sensible (no negatives, rates between 0 and 1)
--    Expected: min values >= 0, max rates <= 1
SELECT
  MIN(incoming_calls)         AS min_incoming,
  MAX(incoming_calls)         AS max_incoming,
  MIN(avg_waiting_time_sec)   AS min_waiting_sec,
  MAX(avg_waiting_time_sec)   AS max_waiting_sec,
  MIN(answer_rate)            AS min_answer_rate,
  MAX(answer_rate)            AS max_answer_rate,
  MIN(service_level_20s)      AS min_service_level,
  MAX(service_level_20s)      AS max_service_level
FROM `call-center-analysis-cb.call_center.clean_data`;
