-- Variant B view: order_state
-- Primary key: order_id
-- Output schema: src/arb/context/schemas.py::OrderState

CREATE MATERIALIZED VIEW order_state AS
WITH latest_order AS (
  SELECT
    order_id,
    LAST_VALUE(customer_id)    AS customer_id,
    LAST_VALUE(status)         AS status,
    LAST_VALUE(total_cents)    AS total_cents,
    LAST_VALUE(currency)       AS currency,
    LAST_VALUE(occurred_at_ms) AS occurred_at_ms
  FROM "retail.orders"
  GROUP BY order_id
),
items AS (
  SELECT
    order_id,
    ARRAY_AGG(STRUCT(
      order_item_id, sku, quantity, unit_price_cents, warehouse_id
    )) AS items
  FROM "retail.order_items"
  GROUP BY order_id
),
inventory_for_items AS (
  -- For each (sku, warehouse) referenced by the order, pick the latest snapshot.
  SELECT
    oi.order_id,
    ARRAY_AGG(STRUCT(
      inv.sku, inv.warehouse_id, inv.quantity_on_hand, inv.occurred_at_ms
    )) AS inventory_for_items
  FROM "retail.order_items" oi
  JOIN (
    SELECT
      sku,
      warehouse_id,
      LAST_VALUE(quantity_on_hand) AS quantity_on_hand,
      LAST_VALUE(occurred_at_ms)   AS occurred_at_ms
    FROM "retail.inventory_snapshots"
    GROUP BY sku, warehouse_id
  ) inv ON inv.sku = oi.sku AND inv.warehouse_id = oi.warehouse_id
  GROUP BY oi.order_id
),
payments AS (
  SELECT
    order_id,
    ARRAY_AGG(STRUCT(
      kind, amount_cents, currency, occurred_at_ms
    ) ORDER BY occurred_at_ms ASC) AS payment_events
  FROM "retail.payment_events"
  GROUP BY order_id
),
open_returns AS (
  SELECT
    order_id,
    LAST_VALUE(return_id) AS open_return_id
  FROM "retail.returns"
  WHERE status IN ('REQUESTED', 'APPROVED', 'RECEIVED')
  GROUP BY order_id
)
SELECT
  o.order_id,
  o.customer_id,
  o.status,
  o.total_cents,
  o.currency,
  o.occurred_at_ms,
  COALESCE(i.items,                 ARRAY[]) AS items,
  COALESCE(inv.inventory_for_items, ARRAY[]) AS inventory_for_items,
  COALESCE(p.payment_events,        ARRAY[]) AS payment_events,
  r.open_return_id
FROM latest_order o
LEFT JOIN items               i   USING (order_id)
LEFT JOIN inventory_for_items inv USING (order_id)
LEFT JOIN payments            p   USING (order_id)
LEFT JOIN open_returns        r   USING (order_id);
