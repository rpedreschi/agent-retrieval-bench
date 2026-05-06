-- Variant B view: returns_eligibility
-- Primary key: return_id
-- Output schema: src/arb/context/schemas.py::ReturnsEligibility
--
-- Eligibility rule: a return is INELIGIBLE for refund if a CHARGEBACK
-- payment event has been observed on the originating order. This is the
-- exact rule the chargeback_downgrade_refund scenario exercises.

CREATE MATERIALIZED VIEW returns_eligibility AS
WITH latest_return AS (
  SELECT
    return_id,
    LAST_VALUE(order_id)       AS order_id,
    LAST_VALUE(status)         AS return_status,
    LAST_VALUE(amount_cents)   AS return_amount_cents,
    LAST_VALUE(occurred_at_ms) AS occurred_at_ms
  FROM "retail.returns"
  GROUP BY return_id
),
order_summary AS (
  SELECT
    order_id,
    LAST_VALUE(STRUCT(
      order_id, status, total_cents, currency, occurred_at_ms
    )) AS order
  FROM "retail.orders"
  GROUP BY order_id
),
order_payments AS (
  SELECT
    order_id,
    ARRAY_AGG(STRUCT(
      kind, amount_cents, currency, occurred_at_ms
    ) ORDER BY occurred_at_ms ASC) AS payment_events,
    BOOL_OR(kind = 'CHARGEBACK')   AS has_chargeback
  FROM "retail.payment_events"
  GROUP BY order_id
)
SELECT
  r.return_id,
  r.order_id,
  r.return_status,
  r.return_amount_cents,
  os.order,
  COALESCE(p.payment_events, ARRAY[])           AS payment_events,
  COALESCE(p.has_chargeback, FALSE)             AS has_chargeback,
  NOT COALESCE(p.has_chargeback, FALSE)         AS eligible_for_refund,
  CASE
    WHEN COALESCE(p.has_chargeback, FALSE) THEN 'chargeback_already_filed'
    ELSE NULL
  END AS ineligibility_reason
FROM latest_return r
LEFT JOIN order_summary  os USING (order_id)
LEFT JOIN order_payments p  USING (order_id);
