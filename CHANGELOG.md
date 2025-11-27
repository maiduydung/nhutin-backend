# Changelog

## 2025-11-27
- Added `IF NOT EXISTS` to all `CREATE TABLE` statements in `schema.psql`.
- Added `Database.initSchema()` method to auto-initialize tables before ingestion.
- Fixed pattern matching in normalizer for Dầu DO, Bơm thuỷ lực, hộp điều khiển.
- Added default units for walking_floor (`set`), controller (`set`), hydraulic_pump (`pcs`).
- Split walking_floor into specific models: `walking_floor_ksd`, `walking_floor_kmd`, `walking_floor_r2dx`.
- Added `price_history` table to schema for tracking unit prices over time.
- Updated `Inventory` class to calculate and store unit prices from import/export data.
- Added `_calculateUnitPrice()` and `_insertPriceHistory()` helper methods.
- Created `docs/agent.md` with comprehensive project documentation.
- Added `type` column to `items` table for item classification.
- Created `services/normalizer.py` with `ItemNormalizer` class:
  - Normalizes item codes (removes quotes, spaces → underscores)
  - Normalizes item names (trims whitespace, removes quotes)
  - Normalizes units to standard format (kg, L, pcs, set, m)
  - Handles common user input typos (riidx → r2dx, kds → ksd, etc.)
  - Walking floor models split: `walking_floor_ksd`, `walking_floor_kmd`, `walking_floor_r2dx`
  - Classifies items into types: `burning_fuel`, `hydraulic_pump`, `controller`, `walking_floor_*`, `aluminum`, `steel`, `stainless_steel`, `steel_box`, `steel_pipe`, `steel_plate`, `steel_square`, `steel_u`, `steel_i`, `galvanized_sheet`, `container`, `other`

## 2025-11-20
- Parse the warehouse report date from row 2 of `data/Tong_hop_ton_kho (65).xlsx`.
- Use the extracted date as `record_date` during inventory ingestion to support idempotent runs.
