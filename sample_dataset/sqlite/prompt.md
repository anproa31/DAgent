# SQLite sample — inventory stock alerts

## Data

Upload `sample_dataset/sqlite/inventory.db`. The sandbox exposes a view named `inventory_inventory` (table `inventory` inside the file).

| Column | Description |
|--------|-------------|
| `sku` | Product SKU (primary key) |
| `product_name` | Display name |
| `warehouse` | Warehouse code (e.g. WH-EAST, WH-WEST) |
| `quantity` | Units on hand |
| `min_threshold` | Minimum stock level |
| `reorder_status` | `adequate`, `low_stock`, or `critical` |
| `last_updated` | Last inventory snapshot date |

## Preset prompt

You have been provided with inventory data from our warehouse management system via the `inventory_inventory` view:

| Column | Description |
|--------|-------------|
| `sku` | Product SKU (primary key) |
| `product_name` | Display name |
| `warehouse` | Warehouse code (e.g. WH-EAST, WH-WEST) |
| `quantity` | Units on hand |
| `min_threshold` | Minimum stock level |
| `reorder_status` | `adequate`, `low_stock`, or `critical` |
| `last_updated` | Last inventory snapshot date |

Conduct a comprehensive "Inventory Stock Alert and Reorder Priority Analysis." We want to identify products that need immediate reorder and understand shortage risk across warehouses.

Your tasks:

1. **Stock alert identification:** List every SKU in `critical` or `low_stock` status with product name, warehouse, quantity, min_threshold, and reorder_status.
2. **Warehouse summary:** Summarize counts of critical and low_stock items by warehouse. Identify which warehouse has the highest shortage risk.
3. **Reorder prioritization:** Rank items needing immediate reorder by urgency (critical first, then low_stock). Flag SKUs where quantity is at or below min_threshold.
4. **Visualizations:** Include a bar chart of alert counts by warehouse and a table of top-priority reorder items.

Provide an Executive Summary, per-warehouse shortage findings, and 3 actionable reorder recommendations ranked by urgency.

## Test prompts

1. Which products need immediate reorder?
2. What is average inventory quantity per warehouse?
3. Which warehouse has the highest shortage risk (most critical/low_stock SKUs)?
4. List all products in `critical` or `low_stock` status.
5. For SKU001, estimate days until stockout if quantity drops at a steady rate since `last_updated`.

## Expected results

- Correct identification of critical and low_stock items.
- Accurate per-warehouse inventory summaries.
- Clear reorder recommendations ranked by urgency.
