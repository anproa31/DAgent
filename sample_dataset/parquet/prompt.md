# Parquet sample — retail & support analytics

## Data

Upload all four files from this folder (`sample_dataset/parquet/`):

| View | File | Description |
|------|------|-------------|
| `customers` | `customers.parquet` | Customer master (id, name, segment, region) |
| `products` | `products.parquet` | Product catalog (id, name, category, unit price) |
| `sales_transactions` | `sales_transactions.parquet` | Orders (customer, product, quantity, amount, date) |
| `support_tickets` | `support_tickets.parquet` | Tickets (customer, subject, priority, status, created_at, resolved_at) |

## Preset prompt

You have been provided with four interconnected datasets representing our retail business and customer support operations:

1. `customers` — customer master (id, name, segment, region)
2. `products` — product catalog (id, name, category, unit price)
3. `sales_transactions` — orders linking customers and products (quantity, amount, date)
4. `support_tickets` — customer support tickets (subject, priority, status, created_at, resolved_at)

Conduct a comprehensive "Retail Revenue and Support SLA Analysis." We want to understand which customers and product categories drive the most revenue, and how support ticket volume and resolution times relate to customer segments.

Your tasks:

1. **Data integration:** Join `sales_transactions` with `customers` and `products` on the appropriate keys. Handle nulls and ensure amount/quantity fields are numeric.
2. **Revenue analysis:** Rank top customers and product categories by total revenue. Break down revenue by customer segment and region where possible.
3. **Support triage:** Review `support_tickets` — identify open tickets that need immediate priority handling. Calculate average resolution time (created_at → resolved_at) by priority level.
4. **Visualizations:** Include a bar chart of revenue by product category, a ranking of top customers by sales amount, and a summary of ticket counts or resolution times by priority.

Provide an Executive Summary, key revenue drivers, support SLA findings, and 3 actionable recommendations to improve revenue focus and ticket response times.

## Test prompts

1. Top 10 customers by total sales amount.
2. Revenue breakdown by product category.
3. Which tickets need immediate priority handling?
4. Average resolution time (created_at → resolved_at) by priority.
5. How many tickets are still open more than 24 hours after creation?

## Expected results

- Correct joins across customers, products, and sales_transactions.
- Accurate revenue aggregations and rankings.
- Support SLA metrics and priority-based ticket triage.
