-- Variant B view: customer_360
-- Primary key: customer_id
-- Refreshed continuously by DeltaStream from the source Kafka topics.
--
-- Output schema is the canonical contract; see
-- src/arb/context/schemas.py::Customer360. Any BYO implementation must
-- produce a payload that validates against that schema.

CREATE MATERIALIZED VIEW customer_360 AS
WITH latest_customer AS (
  SELECT
    customer_id,
    LAST_VALUE(email)         AS email,
    LAST_VALUE(name)          AS name,
    LAST_VALUE(tier)          AS tier,
    LAST_VALUE(updated_at_ms) AS updated_at_ms
  FROM "retail.customers"
  GROUP BY customer_id
),
tier_history AS (
  SELECT
    customer_id,
    ARRAY_AGG(STRUCT(
      from_tier, to_tier, reason, occurred_at_ms
    ) ORDER BY occurred_at_ms ASC) AS tier_history
  FROM "retail.customer_tier_changes"
  GROUP BY customer_id
),
recent_orders AS (
  SELECT
    customer_id,
    ARRAY_AGG(STRUCT(
      order_id, status, total_cents, currency, occurred_at_ms
    ) ORDER BY occurred_at_ms DESC LIMIT 20) AS recent_orders
  FROM "retail.orders"
  GROUP BY customer_id
),
open_tickets AS (
  SELECT
    customer_id,
    ARRAY_AGG(STRUCT(
      ticket_id, order_id, status, subject, occurred_at_ms
    ) ORDER BY occurred_at_ms DESC) AS open_tickets
  FROM "retail.support_tickets"
  WHERE status IN ('OPEN', 'PENDING')
  GROUP BY customer_id
)
SELECT
  c.customer_id,
  c.email,
  c.name,
  c.tier,
  c.updated_at_ms,
  COALESCE(th.tier_history,   ARRAY[]) AS tier_history,
  COALESCE(ro.recent_orders,  ARRAY[]) AS recent_orders,
  COALESCE(ot.open_tickets,   ARRAY[]) AS open_tickets
FROM latest_customer c
LEFT JOIN tier_history  th USING (customer_id)
LEFT JOIN recent_orders ro USING (customer_id)
LEFT JOIN open_tickets  ot USING (customer_id);
