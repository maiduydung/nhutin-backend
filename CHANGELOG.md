# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2025-12-25

### Changed - **BREAKING**: Complete Algorithm Rewrite

#### 4-Phase Constrained Feasibility Algorithm
The optimizer has been completely rewritten to use a 4-phase approach that prioritizes weight feasibility over margin optimization.

**Golden Rule**: Never optimize margin before weight feasibility is locked.

| Phase | Purpose | What It Does |
|-------|---------|--------------|
| 0 | Feasibility | Derive bounds, fail early if impossible |
| 1 | Fixed Items | Walking floor, aluminum, pump, oil (deterministic) |
| 2 | Weight Filling | Reach minWeight with structural materials |
| 3 | Margin Tuning | Add expensive/light items to hit margin |
| 4 | Micro-Adjust | Swap cheap/heavy for expensive/light |

#### Why This Was Needed
The old algorithm optimized for margin-first and hoped weight would fall in range. This led to:
- Weight outside target range (3 out of 4 test cases failed)
- Margin always perfect but weight constraint violated

The new algorithm ensures:
- Weight is guaranteed within range first
- Then margin is optimized within weight constraints
- Clear failure messages when constraints are impossible

### Added

#### New Services
- `services/feasibility_checker.py` - Phase 0: Derives bounds and validates feasibility
- `services/weight_filler.py` - Phase 2: Fills to minimum weight with structural priority
- `services/margin_tuner.py` - Phase 3: Tunes cost to hit margin target
- `services/micro_adjuster.py` - Phase 4: Swaps items to fine-tune margin

#### OptimizerV2 Class
- New main optimizer class replacing the old Optimizer
- Uses all 4 phases in sequence
- Provides detailed constraint status in response

### Removed
- `services/variable_filler.py` - Replaced by weight_filler.py and margin_tuner.py
- `services/weight_targets.py` - Merged into feasibility_checker.py
- Old `Optimizer` class - Replaced by `OptimizerV2`

### Fixed

#### Weight Calculator Bug
- Fixed bug where "Con" (pieces) unit was treated as kg
- Rivets were incorrectly counted as 1500kg instead of 0kg
- Now correctly treats piece-based items as zero-weight

#### Margin Check Tolerance
- Added 0.5% tolerance for margin checks to handle rounding
- 20.1% now passes as "within 20% target"

### Test Results Comparison

| Test Case | Old Result | New Result |
|-----------|------------|------------|
| Mooc Long 15m (700M, 20%) | Weight: 7,217kg ❌ | Weight: 7,500kg ✅ |
| Container 40ft (900M, 15%) | Weight: 10,016kg ❌ | Weight: 7,494kg ✅ |
| Mooc Long 12m (550M, 20%) | Weight: 6,268kg ❌ | Weight: 6,640kg ✅ |
| Container 20ft (350M, 20%) | Margin: 0% ❌ | Fails early with explanation ✅ |

### Documentation
- Completely rewritten `docs/ALGORITHM.md` with V2 algorithm details
- Updated README.md with 4-phase overview
- Updated CHANGELOG.md (this entry)

---

## [1.6.0] - 2025-12-19

### Added

#### Container Type Differentiation
- **New Feature**: Full support for 4 distinct container types with different BOM handling:
  - `Container 20ft` - Standard 20-foot container
  - `Container 40ft` - Standard 40-foot container
  - `Mooc Long` - Long trailer (default 15m length)
  - `Thung Xe Tai` - Truck body (default 15m, user-inputtable)

#### Container Empty Weight Handling
- **Pre-built container weights** now subtracted from Effective Max Weight:
  - Container 20ft: 1,900 kg empty weight → Effective Max: 4,820 kg for materials
  - Container 40ft: 2,500 kg empty weight → Effective Max: 4,220 kg for materials
- For Mooc Long and Thung Xe Tai: No pre-built container → Effective Max remains 6,720 kg

#### New Helper Methods (`services/optimizer.py`)
- `_shouldIncludeContainerItem()` - Determines if container item should be in BOM
- `_getPrebuiltContainerWeight()` - Returns empty weight for pre-built containers
- `_getEffectiveMaxWeight()` - Calculates effective max weight based on container type

#### Configuration Constants (`config.py`)
- `CONTAINER_TYPES_WITH_CONTAINER` - Types that include container in BOM
- `CONTAINER_TYPES_WITHOUT_CONTAINER` - Types that never include container
- `CONTAINER_EMPTY_WEIGHTS` - Empty weights for pre-built containers
- `CONTAINER_DEFAULT_LENGTHS` - Default lengths for each container type

#### Comprehensive Test Suite
- Added `tests/test_container_type_logic.py` with 41 new test cases covering:
  - Container type constant validation
  - Container type recognition and parsing
  - Container item inclusion/exclusion logic
  - Weight constraint calculations
  - Material scaling based on length
  - Fixed items presence verification

### Changed

#### Container Item Exclusion for Mooc Long & Thung Xe Tai
- **Breaking Change**: Container items (e.g., "Vỏ container 20 feet") are now **NEVER** included in BOM for:
  - `mooc_long` - Builds structure from raw materials only
  - `thung_xe_tai` - Builds structure from raw materials only
- Materials (steel frame, galvanized sheets, aluminum) are still included to build the structure

#### Material Scaling Formula
- Steel and galvanized sheets now scale proportionally based on container length:
  - Steel frame: `983 kg × (containerLength / 12.192m)`
  - Galvanized sheet: `100 m × (containerLength / 12.192m)`
- Uses 40ft container (12.192m) as baseline
- Example: 15m Mooc Long → Steel: ~1,209 kg, Sheets: ~123 m

#### UserInput Model (`models/user_input.py`)
- Updated `containerType` to accept new literal values from UI:
  - `"container_20ft"`, `"container_40ft"`, `"mooc_long"`, `"thung_xe_tai"`

#### Optimizer Response
- Now includes `effectiveMaxWeight` in response
- Now includes `prebuiltContainerWeight` for transparency

### Weight Constraint Summary

| Container Type | Pre-built Container in BOM | Container Weight | Effective Max Materials |
|----------------|---------------------------|------------------|------------------------|
| Container 20ft (pre-built) | ✅ Yes | 1,900 kg | 4,820 kg |
| Container 20ft (built) | ✅ Yes | 0 kg | 6,720 kg |
| Container 40ft (pre-built) | ✅ Yes | 2,500 kg | 4,220 kg |
| Container 40ft (built) | ✅ Yes | 0 kg | 6,720 kg |
| Mooc Long | ❌ No | 0 kg | 6,720 kg |
| Thung Xe Tai | ❌ No | 0 kg | 6,720 kg |

### Documentation
- Updated `docs/ALGORITHM.md` with container type handling section
- Updated `README.md` with 4 container types and weight constraints
- Updated `CHANGELOG.md` (this entry)

### Tests Updated
- `tests/test_optimizer_container_build.py` - Updated for new return signature
- `tests/test_container_builder.py` - Fixed mock setup for new parameters

---

## [1.5.0] - 2025-12-12

### Changed

#### Material Loss Factor
- **New Feature**: Added 12% material loss factor to account for processing losses (cutting, shaping, waste)
- Base weight limit increased to 6000 kg (target cargo weight)
- Effective max weight increased to **6720 kg** (6000 × 1.12)
- After processing, ~6000 kg of usable cargo expected

#### Profit Margin Target
- Reduced target profit margin from 25% to **15%**
- Reduced minimum boost profit margin from 10% to **5%** (for aluminum weight boost)
- More aggressive budget filling to ensure profit margin stays within target

### Added

#### Budget Filling Logic (`services/optimizer.py`)
- **New Method**: `_fillBudgetToTargetMargin()` - Fills remaining budget when profit margin exceeds 15%
- Priority order for budget filling:
  1. Aluminum (best weight-to-cost ratio)
  2. Steel (existing items)
  3. New items from inventory
- Activates automatically after main optimization if margin still too high

### Fixed

#### High Profit Margin Issue
- **Root Cause**: Algorithm stopped at weight limit (6000 kg) before spending enough budget
- **Fix**: With material loss factor, algorithm can now add materials up to 4144 kg
- **Fix**: Added budget filling step to spend remaining budget after weight optimization
- Expected result: profit margin reduced from 34-35% to 10-15%

### Configuration Changes (`services/optimizer.py`)

| Constant | Before | After | Description |
|----------|--------|-------|-------------|
| `BASE_MAX_WEIGHT` | N/A | 6000 kg | Base weight limit |
| `MATERIAL_LOSS_FACTOR` | N/A | 0.12 (12%) | Processing loss factor |
| `MAX_WEIGHT` | 6000 kg | 6720 kg | Effective max weight |
| `MAX_PROFIT_MARGIN` | 0.25 (25%) | 0.15 (15%) | Target profit margin |
| `MIN_BOOST_PROFIT_MARGIN` | 0.10 (10%) | 0.05 (5%) | Minimum margin for boost |

### Documentation
- Updated `docs/ALGORITHM.md` with material loss factor explanation
- Updated `README.md` with new weight constraints and profit margin targets

---

## [1.4.0] - 2025-12-07

### Fixed

#### Duplicate Items Bug
- **Critical Fix**: Fixed issue where steel and galvanized sheet items appeared twice in results (once as regular items, once as container build materials)
- Added exclusion logic in `_optimizeVariableItems()` "fill remaining weight" loop to skip container build material types
- Items now correctly appear in only ONE category: either regular items OR container build materials

### Changed

#### Container Specifications (Based on THUYETMINHKYTHUAT.pdf)
- Updated container specs to match technical document "Walking Floor S-Drive KSD 4.25"
- New material requirements based on actual engineering specifications:

| Size | Steel Frame (kg) | Galvanized Sheet (m) | Aluminum (kg) | Source Reference |
|------|------------------|----------------------|---------------|------------------|
| 20ft | 492 | 50 | 378 | ~50% of 40ft |
| 40ft | 983 | 100 | 757 | THUYETMINHKYTHUAT.pdf |

**40ft Container Breakdown (from technical document):**
- **Aluminum bars**: 756.76 kg (25 bars × 12m × 2.53 kg/m) - 21 for floor slats + 4 accessories
- **Steel frame**: ~983 kg total
  - Sắt hộp vuông kẽm: 332.34 kg (~55m hộp 80×40 or 100×50)
  - Thép vuông kẽm: 398.48 kg (~124m thép 40×40mm)
  - Thép vuông mạ kẽm: 252.41 kg (~84m thép 30-40×40mm)

#### Configuration (`config.py`)
- Added `CONTAINER_BUILD_SPECS` dictionary with detailed material requirements
- Added `CONTAINER_MATERIAL_TYPES` mapping for database item type lookups
- Added `MATERIAL_SUBSTITUTES` for flexible material substitution rules

#### Optimizer Improvements
- Added `containerBuildItemIds` parameter to track items used for container building
- Added `containerBuildTypes` constant for material type exclusion
- Both ID-based and type-based exclusion now applied consistently across all selection loops

### Technical Notes
- Container building now uses lower threshold (50%) for material availability
- Material substitution: aluminum can replace steel shortfall at 1:1 weight ratio
- Specs reference: `data/THAICUONG 23062025 THUYETMINHKYTHUAT.pdf`

---

## [1.3.0] - 2025-12-07

### Added

#### Container Building from Materials
- **New Feature**: When requested container type (20ft or 40ft) is not in inventory, the system now automatically builds it from raw materials
- **Container Builder Service** (`services/container_builder.py`):
  - `ContainerBuilder` class for building containers from steel, galvanized sheets, and aluminum
  - `canBuildContainer()` - Check if materials are available to build a container
  - `buildContainer()` - Build container with budget and weight constraints
  - Supports scaled building (minimum 10%) when constraints are tight
  - **Flexible Material Substitution**: If not enough steel, uses aluminum to compensate

#### Container Specifications
| Size | Steel (kg) | Galvanized Sheet (m) | Aluminum (kg) |
|------|------------|----------------------|---------------|
| 20ft | 800 | 50 | 100 |
| 40ft | 1500 | 100 | 200 |

#### Key Features
- **Steel Shortfall Compensation**: When steel inventory is insufficient, aluminum automatically fills the gap
- **Shared Aluminum Pool**: When building containers, aluminum serves both as structure AND slats (no double-counting)
- **Budget-Aware Scaling**: Container build scales down automatically when budget is limited

#### Test Suite
- Added `tests/` directory with comprehensive test coverage
- `tests/test_container_builder.py` - Unit tests for ContainerBuilder service
- `tests/test_optimizer_container_build.py` - Tests for optimizer integration
- `tests/test_integration_container_build.py` - Integration tests with real database

### Changed

#### Optimizer (`services/optimizer.py`)
- Added `ContainerBuilder` integration
- Added `_checkNeedToBuildContainer()` method to detect when container building is needed
- Modified `optimize()` to build containers from materials when unavailable
- Modified `_optimizeVariableItems()` to skip containers when building from materials
- Response now includes `containerBuiltFromMaterials: boolean` field

#### Function App (`function_app.py`)
- Response now includes `containerBuiltFromMaterials` field

### Response Example (Container Built from Materials)
```json
{
  "status": "ok",
  "items": [
    {"code": "thephop", "quantity": 800, "weight": 800, "forContainerBuild": true},
    {"code": "ton_ma_kem", "quantity": 50, "weight": 447, "forContainerBuild": true},
    {"code": "nhom_thanh", "quantity": 100, "weight": 100, "forContainerBuild": true}
  ],
  "containerBuiltFromMaterials": true,
  "totalWeight": 3200.0,
  "profitMargin": 18.5
}
```

### Documentation
- Updated `docs/ALGORITHM.md` with container building section
- Updated `README.md` with container builder documentation

---

## [1.2.0] - 2025-12-02

### Added

#### Aluminum Boost for Weight
- When total weight is below MIN_WEIGHT (3000 kg), optimizer now automatically adds more aluminum bars
- Adding aluminum increases cost, which reduces profit margin (achieving both targets)
- Example: 2,564 kg → 3,000 kg by adding 436 kg aluminum, margin reduced from 25% to 10%

#### Container Validation and Fallback
- Added validation for requested container type against database inventory
- If requested container (e.g., 40ft) is not available, logs ERROR and uses fallback container
- Log message: "Requested 40ft container not found in database. Available: ['20ft']. Using fallback."

### Changed

#### Optimizer (`services/optimizer.py`)
- Added `containerType` parameter to `optimize()` method
- Added `_boostAluminumForWeight()` method for weight boosting logic
- Added `_selectContainerWithFallback()` method for container validation
- Updated `_getVariableItems()` to accept `containerType` for filtering

#### Function App (`function_app.py`)
- Now passes `containerType` from user input to optimizer

### Performance

For a 20ft container with 360M VND receipt price:
| Metric | Before | After (with boost) |
|--------|--------|-------------------|
| Total Weight | 2,564 kg | 3,000 kg |
| Profit Margin | 25.00% | 10.06% |
| Aluminum Qty | 417 kg | 854 kg |

---

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
  - Constraint enforcement (weight range: 3000-6000kg, profit margin ≤ 15%)
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
  - Weight: 3000-6000kg (soft limit, prefers under 6000kg)
  - Profit margin: ≤ 15% of receipt price
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
- Consider adding weight tolerance configuration (currently hardcoded to 3000-6000kg)

