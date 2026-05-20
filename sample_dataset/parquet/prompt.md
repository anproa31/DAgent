# Test Scenario 3: Support Ticket Analytics

## Objective
Test AI agent's ability to analyze support tickets, track SLA, prioritize processing.

## Input Data
- File: `scenario_03_support_tickets/data.csv`
- Schema: ticket_id, customer_id, subject, priority, status, created_at, resolved_at

## Test Prompts
1. Which tickets need immediate priority handling?
2. What is average resolution time for tickets?
3. Which priority level has most tickets?
4. How many tickets remain open after 24 hours?
5. What are common support ticket themes?

## Expected Results
- Identification of high/critical priority open tickets
- Accurate calculation from created_at to resolved_at
- Ticket categorization by theme/status
