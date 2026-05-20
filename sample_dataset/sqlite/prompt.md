# Test Scenario 2: Inventory Stock Alerts

## Objective
Test AI agent's ability to detect stock alerts and predict reorder needs.

## Input Data
- File: `scenario_02_inventory_stock/data.csv`
- Schema: sku, product_name, warehouse, quantity, min_threshold, reorder_status, last_updated

## Test Prompts
1. Which products need immediate reorder?
2. What is average inventory per warehouse?
3. When will SKU001 run out at current consumption rate?
4. Which warehouse has higher shortage risk?
5. List all products in critical/low_stock status?

## Expected Results
- Correct identification of out-of-stock/alert items
- Accurate per-warehouse inventory calculations
- Early warning for low-stock products
