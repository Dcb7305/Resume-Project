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
  AND `Answered Calls` <= `Incoming Calls`;   -- drop impossible rows
