# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2025-12-02

### Added

#### Zero-Weight Item Support
- **Container Support**: Containers are now included in optimization as zero-weight items
  - Container weight set to 0 (packaging, not cargo - doesn't count toward weight constraint)
  - Helps fill budget and reduce profit margin
  - Example: Adding a 34M VND container reduced profit margin from 34.48% to 26.48%

#### Extended Variable Item Types
- Optimizer now supports 10 variable item types:
  - `steel_box`, `steel_i`, `steel_square`, `steel_u`, `steel_pipe`, `steel_plate`
  - `galvanized_sheet`, `stainless_steel`, `hydraulic_pump`, `container`

### Changed

#### Optimization Algorithm (`services/optimizer.py`)
- **Two-Pass Variable Item Selection**:
  1. First pass: Select weight-contributing items (steel, sheets) by weight-to-cost ratio
  2. Second pass: Add zero-weight items (containers) to fill remaining budget
- This ensures expensive items that don't add weight are used to minimize profit margin

#### Weight Calculator (`services/weight_calculator.py`)
- Added `CONTAINER_WEIGHT` constant (set to 0 for both 20ft and 40ft)
- Added `HYDRAULIC_PUMP_WEIGHT` constant (50 kg)
- Updated `calculateItemWeight()` to handle containers and hydraulic pumps

### Performance Improvement

For a KSD container with 425M VND receipt price:
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Profit Margin | 34.48% | 26.48% | -8.00 pp |
| Total Cost | 278.4M VND | 312.4M VND | +34M VND |
| Items Used | 7 | 8 | +1 (container) |

### Documentation
- Updated `docs/ALGORITHM.md` with zero-weight item handling
- Updated `README.md` with new variable item types
- Added this changelog entry

---

## [1.0.0] - 2025-01-XX

### Added

#### Core Optimization System
- **Weight Calculator Service** (`services/weight_calculator.py`):
  - `WeightCalculator` class for calculating weights of different item types
  - Walking floor weight lookup from config (R2DX: 751kg, KSD: 503kg, KMD: 502kg)
  - Aluminum bar weight calculation using `aluminum_bar_constants` table
  - Galvanized sheet weight calculation formula (thickness × width × 7850 / 1,000,000)
  - Support for multiple unit types: `kg`, `set`, `m` (meters)

- **Optimizer Service** (`services/optimizer.py`):
  - `Optimizer` class implementing container weight and profit optimization
  - Fixed items selection (walking floor + aluminum bars)
  - Variable items optimization (steel, galvanized sheets)
  - Greedy algorithm with weight-to-cost ratio prioritization
  - Constraint enforcement (weight range: 3000-3700kg, profit margin ≤ 20%)
  - Inventory availability checking

#### API Enhancements
- **Process Receipt Endpoint** (`POST /api/process_receipt`):
  - Full optimization pipeline integration
  - Returns optimized item list with detailed weights and costs
  - Calculates and validates profit margin
  - Response includes: items array, totalWeight, totalCost, receiptPrice, profit, profitMargin

#### Configuration
- **Walking Floor Constants** (`config.py`):
  - `WALKING_FLOORS` dictionary with weight and type mappings
  - Supports R2DX, KSD, and KMD walking floor types
  - Structure: `{modelType: {"type": "walking_floor_xxx", "weight": kg}}`

#### Database Schema
- **Aluminum Bar Constants Table** (`aluminum_bar_constants`):
  - Stores density and bars-per-container data
  - Supports different slat sizes (97mm, 112mm)
  - Used for calculating aluminum bar weights dynamically

### Changed

- **User Input Model** (`models/user_input.py`):
  - Added `receiptPrice` field (required, float)
  - Updated validation to include receipt price

- **Process Receipt Endpoint** (`function_app.py`):
  - Replaced simple validation response with full optimization
  - Now returns optimized item selection instead of just echoing input
  - Integrated `Optimizer` service

### Technical Details

#### Weight Calculation Formulas

1. **Walking Floor Sets**:
   - Weight from config: `WALKING_FLOORS[itemModelType]["weight"]`
   - Always 1 set per container

2. **Aluminum Bars**:
   - Formula: `containerLength × density_kg_per_m × bars_per_container`
   - Density from `aluminum_bar_constants` table based on `slatType`
   - Falls back to lower density if inventory insufficient

3. **Steel Items** (unit = "kg"):
   - Weight = quantity (quantity is already in kilograms)

4. **Galvanized Sheets** (unit = "m"):
   - Formula: `Thickness (mm) × Width (mm) × 7850 / 1,000,000`
   - Dimensions parsed from item name
   - Example: "0.95 x 1200" → 0.95mm × 1200mm × 7850 / 1,000,000 = 8.9445 kg/m

#### Optimization Algorithm

- **Phase 1 - Fixed Items**:
  - Selects 1 walking floor set (based on `itemModelType`)
  - Calculates and includes aluminum bars (based on `containerLength` and `slatType`)

- **Phase 2 - Variable Items**:
  - Groups items by type for variety
  - Selects best item from each type (weight-to-cost ratio)
  - Fills remaining weight with best-ratio items
  - Respects budget constraint (max cost = receiptPrice × 0.8)

- **Constraints**:
  - Weight: 3000-3700kg (soft limit, prefers under 3700kg)
  - Profit margin: ≤ 20% of receipt price
  - Inventory: Uses `final_quantity` from latest records

### Documentation

- Updated README.md with:
  - Complete API endpoint documentation
  - Optimization algorithm details
  - Weight calculation formulas
  - Database schema updates
  - Implementation status updates

### Files Added

- `services/weight_calculator.py` - Weight calculation utilities
- `services/optimizer.py` - Optimization engine
- `CHANGELOG.md` - This changelog file

### Files Modified

- `function_app.py` - Integrated optimizer service
- `models/user_input.py` - Added receiptPrice field
- `config.py` - Added WALKING_FLOORS dictionary
- `README.md` - Comprehensive documentation updates

### Known Limitations

- Optimization algorithm is greedy (not optimal, but fast and readable)
- Weight target may not always be perfectly achieved if budget is too restrictive
- Profit margin calculation uses latest inventory prices (may not reflect current market prices)
- Aluminum inventory checking uses aggregated "Nhôm_thanh_none" item (poor record keeping)

### Future Improvements

- Consider implementing more sophisticated optimization algorithms (e.g., linear programming)
- Add support for multiple optimization solutions/rankings
- Implement caching for frequently accessed data
- Add unit tests for weight calculations and optimization logic
- Consider adding weight tolerance configuration (currently hardcoded to 3000-3700kg)

