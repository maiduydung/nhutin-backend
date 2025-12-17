# Container Weight Optimization Algorithm

## Problem Classification

This is a **Constrained Multiple Knapsack Problem** variant with the following characteristics:

- **Problem Type**: Multi-constraint optimization
- **Algorithm**: Greedy heuristic with weight-to-cost ratio prioritization
- **Complexity**: O(n log n + k × n) where n = number of items, k = iterations (typically < 10)

### Constraints

1. **Weight Constraint**: Total weight must be between 3000-6720 kg
   - Base limit: 6000 kg
   - Material loss factor: 12% (allows extra weight to compensate for processing losses)
   - Effective max weight: 6000 × 1.12 ≈ 6720 kg
2. **Budget Constraint**: Total cost ≤ 80% of receipt price (profit margin ≤ 20%)
3. **Variety Constraint**: Must use multiple item types (never select only one type)
4. **Availability Constraint**: Cannot exceed `final_quantity` from inventory records

## Algorithm Overview

The optimizer uses a **two-phase greedy approach**:

1. **Phase 1: Fixed Items** - Always included (no optimization needed)
2. **Phase 2: Variable Items** - Greedy selection with ratio-based prioritization

## Phase 1: Fixed Items Selection

These items are **always included** in every container configuration:

### 1. Walking Floor Set
- **Quantity**: Always 1 set
- **Selection**: Based on `itemModelType` from user input
  - `"R2DX"` → Select item with `type = "walking_floor_r2dx"` (weight: 751 kg)
  - `"KSD"` → Select item with `type = "walking_floor_ksd"` (weight: 503 kg)
  - `"KMD"` → Select item with `type = "walking_floor_kmd"` (weight: 502 kg)
- **Weight**: Retrieved from `config.WALKING_FLOORS` dictionary
- **Cost**: `unitPrice × 1` (unitPrice from latest inventory record)

### 2. Aluminum Bars
- **Quantity**: Calculated dynamically based on `slatType` and `thickness`
- **Weight Formula**: `containerLength × density_kg_per_m × bars_per_container`
- **Selection Logic**:
  1. Look up `aluminum_bar_constants` table using both `slatType` (97mm or 112mm) AND `thickness` (6mm or 8mm)
  2. Query returns exact match for size_mm and thickness_mm
  3. If no exact match, falls back to any available thickness for that size
- **Cost**: Uses `unitPrice` from aluminum inventory item
- **Note**: Quantity in kg equals the calculated weight

**Aluminum Bar Constants Table:**
| size_mm | thickness_mm | density_kg_per_m | bars_per_container |
|---------|--------------|------------------|-------------------|
| 97      | 6            | 2.313            | 24                |
| 112     | 6            | 2.529            | 21                |
| 112     | 8            | 3.313            | 21                |

**Example Calculations (40ft container, 12.192m):**
- 97mm/6mm: 12.192 × 2.313 × 24 = **676.77 kg**
- 112mm/6mm: 12.192 × 2.529 × 21 = **647.29 kg**
- 112mm/8mm: 12.192 × 3.313 × 21 = **848.12 kg**

## Phase 2: Variable Items Optimization

### Supported Variable Item Types
```python
variableTypes = [
    'steel_box', 'steel_i', 'steel_square', 'steel_u', 'steel_pipe', 'steel_plate',
    'galvanized_sheet', 'stainless_steel', 'hydraulic_pump', 'container'
]
```

### Step 1: Separate Items by Weight Contribution
Items are separated into two categories:
1. **Weight-contributing items**: Items where `weightPerUnit > 0` (steel, galvanized sheets)
2. **Zero-weight items**: Items where `weightPerUnit = 0` (containers - they're packaging, not cargo)

```python
zeroWeightItems = []   # e.g., containers
weightItems = []       # e.g., steel, galvanized sheets
```

### Step 2: Select Weight-Contributing Items (by type for variety)
For each item type with weight > 0:
1. Calculate weight-to-cost ratio for all items: `ratio = weight_per_unit / unit_price`
2. Select item with **highest ratio** (most efficient: kg per VND)
3. Calculate maximum quantity:
   ```python
   weightSpaceLeft = MAX_WEIGHT - currentTotalWeight
   maxWeightQuantity = weightSpaceLeft / weightPerUnit
   maxBudgetQuantity = (maxCost - currentCost) / unitPrice
   maxQuantity = min(availableQuantity, maxWeightQuantity, maxBudgetQuantity)
   ```
4. Take **maximum possible quantity** (greedy approach)
5. Add to selected items

### Step 3: Add Zero-Weight Items to Fill Budget
After selecting weight-contributing items, add zero-weight items (like containers) to fill remaining budget:

```python
for item in zeroWeightItems:
    if currentCost >= maxCost:
        break
    budgetRemaining = maxCost - currentCost
    maxQty = min(item["availableQuantity"], int(budgetRemaining / item["unitPrice"]))
    if maxQty > 0:
        selectedItems.append(item)
        currentCost += item["unitPrice"] * maxQty
```

This ensures expensive items that don't add weight (like container shells) are used to fill the budget gap and reduce profit margin.

### Step 4: Fill Remaining Weight
Iteratively fill remaining weight capacity:

1. **Sort all weight-contributing items** by weight-to-cost ratio (descending)
2. **For each item** (best ratio first):
   - Check if already selected (can add more quantity)
   - Calculate how much more can be added
   - Take maximum possible (respecting weight, budget, availability)
   - Update selected items
3. **Continue until**:
   - Weight reaches MAX_WEIGHT (~6720kg with material loss factor), OR
   - Budget exhausted (cost ≥ maxCost), OR
   - No more items can be added
4. **If profit margin still too high** (> 20%):
   - Add more materials to fill remaining budget
   - Priority: aluminum first, then steel, then others

### Step 5: Iteration Loop
The algorithm uses a **while loop** (max 20 iterations) to ensure all items are considered:
- Recalculates `currentTotalWeight` and `currentCost` each iteration
- Stops when no progress made (weight and cost unchanged)

## Weight Calculation Methods

### 1. Walking Floor Sets (`unit = "set"`)
```python
weight = WALKING_FLOORS[itemModelType]["weight"] × quantity
```
- R2DX: 751 kg per set
- KSD: 503 kg per set
- KMD: 502 kg per set

### 2. Aluminum Bars
```python
weight = containerLength × density_kg_per_m × bars_per_container
```
- Density and bars from `aluminum_bar_constants` table
- Selected based on `slatType` (97mm or 112mm) AND `thickness` (6mm or 8mm)

### 3. Steel Items (`unit = "kg"`)
```python
weight = quantity  # Quantity is already in kilograms
```
- Applies to: `steel_box`, `steel_i`, `steel_square`, `steel_u`, `steel_pipe`, `steel_plate`, `stainless_steel`

### 4. Galvanized Sheets (`unit = "m"`)
```python
weight_per_meter = thickness_mm × width_mm × 7850 / 1,000,000
weight = quantity × weight_per_meter
```
- Dimensions extracted from item name using regex: `(\d+\.?\d*)\s*x\s*(\d+)`
- Example: "Tôn mạ kẽm 0.95 x 1200" → 0.95mm × 1200mm × 7850 / 1,000,000 = 8.9445 kg/m
- Density of galvanized steel: 7850 kg/m³

### 5. Containers (`unit = "set"`)
```python
weight = 0  # Containers don't count toward weight constraint
```
- **Important**: Container weight is set to 0 because it's the packaging, not cargo
- The weight constraint (3000-6000kg) applies to cargo that goes INTO the container
- Containers are high-value items used to fill budget and reduce profit margin

### 6. Hydraulic Pumps (`unit = "cái" or "pcs"`)
```python
weight = quantity × 50  # Approximately 50 kg per unit
```

## Profit Margin Calculation

```python
totalCost = sum(item["quantity"] × item["unitPrice"] for all items)
profit = receiptPrice - totalCost
profitMargin = (profit / receiptPrice) × 100%
```

**Constraint**: `profitMargin ≤ 20%` (equivalent to `totalCost ≤ receiptPrice × 0.80`)

### Material Loss Factor

Due to material processing losses (cutting, shaping, waste), the algorithm allows extra weight:

```python
BASE_MAX_WEIGHT = 6000  # kg (target cargo weight)
MATERIAL_LOSS_FACTOR = 0.12  # 12% loss during processing
MAX_WEIGHT = BASE_MAX_WEIGHT × (1 + MATERIAL_LOSS_FACTOR)  # ~6720 kg
```

This means:
- Base cargo weight target: 6000 kg
- With 12% material loss factor: can add up to 6720 kg of materials
- After processing, expect ~6000 kg of usable cargo

## Algorithm Pseudocode

```
function optimize(containerLength, itemModelType, slatType, thickness, receiptPrice):
    // Phase 1: Fixed Items
    walkingFloor = getWalkingFloor(itemModelType)  // 1 set
    aluminumWeight = calculateAluminumWeight(containerLength, slatType, thickness)
    aluminumItem = getAluminumItem(aluminumWeight)
    
    fixedWeight = walkingFloor.weight + aluminumWeight
    fixedCost = walkingFloor.cost + aluminumItem.cost
    maxCost = receiptPrice × 0.80  // 20% profit margin
    
    // Phase 2: Variable Items
    variableItems = getVariableItems()  // All variable types including container
    selectedItems = []
    currentWeight = fixedWeight
    currentCost = fixedCost
    
    // Separate by weight contribution
    zeroWeightItems = items where weightPerUnit == 0  // containers
    weightItems = items where weightPerUnit > 0       // steel, sheets
    
    // Step 1: Select weight-contributing items by type for variety
    itemsByType = groupByType(weightItems)
    for each type in itemsByType:
        bestItem = item with highest (weightPerUnit / unitPrice)
        maxQty = min(availableQty, weightSpaceLeft, budgetLeft)
        addItem(bestItem, maxQty)
    
    // Step 2: Add zero-weight items to fill budget (reduces profit margin)
    for each item in zeroWeightItems:
        if currentCost >= maxCost: break
        budgetLeft = maxCost - currentCost
        maxQty = min(availableQty, budgetLeft / unitPrice)
        addItem(item, maxQty)
    
    // Step 3: Fill remaining weight with best-ratio items
    sort weightItems by (weightPerUnit / unitPrice) descending
    
    while currentWeight < MAX_WEIGHT and currentCost < maxCost:
        for each item in sortedItems:
            if canAddMore(item):
                maxQty = calculateMaxQuantity(item)
                addItem(item, maxQty)
                break
        if noProgress:
            break
    
    return selectedItems
```

## Why Greedy Algorithm?

### Advantages
- **Fast**: O(n log n) for sorting + O(n) iterations
- **Simple**: Easy to understand and maintain
- **Practical**: Works well for this use case
- **Real-time**: Suitable for API responses

### Disadvantages
- **Not Optimal**: Doesn't guarantee the best solution
- **Local Optima**: May get stuck in suboptimal solutions
- **No Backtracking**: Can't undo decisions

### Why Not Other Algorithms?

1. **Dynamic Programming**: Optimal but O(n × W × B) complexity - too slow for real-time API
2. **Integer Linear Programming**: Optimal but requires solver library, more complex
3. **Genetic Algorithms**: Can find better solutions but much slower and more complex
4. **Branch and Bound**: Optimal but exponential worst-case complexity

For this use case, **greedy is the right choice** because:
- Solution quality is sufficient (fills weight range effectively)
- Speed is important (API response time)
- Multiple constraints make exact optimization complex
- Real-world inventory constraints make perfect optimization less critical

## Key Implementation Details

### Unit Price Retrieval
**CRITICAL**: Always read `row[7]` (unit_price) from SQL query, NOT `row[6]` (final_value)
```python
# SQL returns: id, code, name, unit, type, final_quantity, final_value, unit_price
unitPrice = float(row[7])  # ✅ Correct
unitPrice = float(row[6])  # ❌ Wrong (this is total value, not per unit)
```

### Weight-to-Cost Ratio
```python
ratio = weightPerUnit / unitPrice  # kg per VND
```
Higher ratio = more weight per VND spent = better efficiency

### Maximum Quantity Calculation
```python
maxWeightQuantity = int((MAX_WEIGHT - currentTotalWeight) / weightPerUnit)
maxBudgetQuantity = int((maxCost - currentCost) / unitPrice)
maxQuantity = min(availableQuantity, maxWeightQuantity, maxBudgetQuantity)
```

### Iteration Stopping Condition
```python
if currentTotalWeight == previousWeight and currentCost == previousCost:
    break  # No progress made, stop iterating
```

## Example Walkthrough

**Input**:
- `containerLength`: 12.192 m
- `itemModelType`: "R2DX"
- `slatType`: "97mm"
- `thickness`: 6 (mm)
- `receiptPrice`: 600,000,000 VND

**Phase 1**:
- Walking floor: R2DX set (751 kg, 248,802,602 VND)
- Aluminum (97mm/6mm): 12.192 × 2.313 × 24 = 676.8 kg (83,540,339 VND)
- Fixed total: 1427.8 kg, 332,342,941 VND

**Phase 2**:
- Available budget: 450,000,000 - 332,342,941 = 117,657,059 VND
- Available weight: 6000 - 1427.8 = 4572.2 kg
- Select items by ratio:
  1. `thephop`: 1 kg / 16,640 VND = 0.0000601 ratio → 483 kg
  2. `THÉP_HỘP_KẼM`: 1 kg / 16,561 VND = 0.0000604 ratio → 249 kg
  3. `Tôn_mạ_kẽm_1.50x1250`: 14.72 kg / 236,364 VND = 0.0000623 ratio → 54 m (794.81 kg)
  4. Continue until weight/budget exhausted...

**Result**: ~3625 kg total weight, within 3000-6000 kg range

## Aluminum Boost for Weight

When total weight is below MIN_WEIGHT (3000 kg) after optimization, the algorithm automatically adds more aluminum bars:

```python
if totalWeight < MIN_WEIGHT:
    weightNeeded = MIN_WEIGHT - totalWeight
    additionalAluminum = min(weightNeeded, availableInventory, maxAffordable)
    aluminumItem["quantity"] += additionalAluminum
```

**Key insight**: Adding aluminum INCREASES cost which DECREASES profit margin. So boosting aluminum achieves both:
1. Increases weight toward MIN_WEIGHT target
2. Reduces profit margin (more efficient use of receipt price)

**Example**:
- Before boost: 2,564 kg, 25.00% margin
- After boost: 3,000 kg, 10.06% margin (added 436 kg aluminum)

## Container Validation and Fallback

The optimizer validates the requested container type against available inventory:

```python
if requestedContainer not in database:
    logger.error(f"Requested {size}ft container not found. Using fallback.")
    return availableContainers[0]  # Use any available container
```

**Example**:
- Request: `container_40ft` (not in DB)
- Error logged: "Requested 40ft container not found. Available: ['20ft']"
- Fallback: Uses "Vỏ container 20 feet đã qua sử dụng"

## Container Building from Materials

When the requested container type (20ft or 40ft) is not available in inventory, the optimizer automatically builds a container from raw materials.

### Container Building Specifications

Based on **THUYETMINHKYTHUAT.pdf** - Walking Floor S-Drive KSD 4.25" system:

```python
CONTAINER_BUILD_SPECS = {
    "20ft": {
        "length_m": 6.096,
        "steel_frame_kg": 492,
        "galvanized_sheet_m": 50,
    },
    "40ft": {
        "length_m": 12.192,
        "steel_frame_kg": 983,    # Combined: 332.34 + 398.48 + 252.41 kg
        "galvanized_sheet_m": 100,
    },
}
```

**Note**: Aluminum is calculated dynamically based on `slatType` and `thickness` (not fixed values).
The formula `containerLength × density_kg_per_m × bars_per_container` is applied using values from `aluminum_bar_constants` table.

**40ft Material Breakdown (from technical document):**

| Material | Weight | Description |
|----------|--------|-------------|
| Nhôm thanh #000 | 756.76 kg | 25 bars × 12m × 2.53 kg/m (21 for slats + 4 accessories) |
| Sắt hộp vuông kẽm | 332.34 kg | ~55m hộp 80×40 or 100×50 (main beams) |
| Thép vuông kẽm | 398.48 kg | ~124m thép 40×40mm (cross bracing) |
| Thép vuông mạ kẽm | 252.41 kg | ~84m thép 30-40×40mm (frame accessories) |
```

### Building Process

1. **Check Container Availability**:
   - Parse container type from request (e.g., "container_40ft" → "40ft")
   - Check if matching container exists in variable items
   - If not found, trigger container building

2. **Material Gathering**:
   - Steel: Collected from any steel type (steel_box, steel_i, etc.)
   - Galvanized sheets: Collected with weight calculation
   - Aluminum: Collected from aluminum inventory

3. **Constraints**:
   - Materials must be at least 90% of required quantity
   - Building cost must fit within remaining budget
   - Building weight must fit within remaining weight capacity
   - Scaled building allowed if constraints tight (minimum 50%)

4. **Response**:
   - `containerBuiltFromMaterials: true` indicates container was built
   - Built materials appear in items list with `forContainerBuild: true` flag

### Example: Building 40ft Container

```python
# Request: container_40ft (not in inventory)
# Response includes:
{
    "containerBuiltFromMaterials": true,
    "items": [
        # ... fixed items (walking floor, aluminum bars) ...
        {"code": "thephop", "quantity": 1500, "weight": 1500, "forContainerBuild": true},
        {"code": "ton_ma_kem", "quantity": 100, "weight": 894.5, "forContainerBuild": true},
        {"code": "nhom_thanh", "quantity": 200, "weight": 200, "forContainerBuild": true},
    ]
}
```

## Future Improvements

1. **Multi-objective Optimization**: Balance weight, cost, and variety more intelligently
2. **Backtracking**: Allow undoing selections if better combination found
3. **Multiple Solutions**: Generate top-N solutions for user to choose
4. **Weight Tolerance Configuration**: Make 3000-6000kg range configurable
5. **Item Priority Weights**: Allow certain items to be prioritized over others
6. **Caching**: Cache weight calculations for frequently used items

## References

- **Knapsack Problem**: https://en.wikipedia.org/wiki/Knapsack_problem
- **Greedy Algorithm**: https://en.wikipedia.org/wiki/Greedy_algorithm
- **Bin Packing Problem**: https://en.wikipedia.org/wiki/Bin_packing_problem

