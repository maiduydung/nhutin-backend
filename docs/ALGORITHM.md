# Container Weight Optimization Algorithm

## Problem Classification

This is a **Constrained Multiple Knapsack Problem** variant with the following characteristics:

- **Problem Type**: Multi-constraint optimization
- **Algorithm**: Greedy heuristic with weight-to-cost ratio prioritization
- **Complexity**: O(n log n + k × n) where n = number of items, k = iterations (typically < 10)

### Constraints

1. **Weight Constraint**: Total weight must be between 3000-3700 kg (soft limit at 3700kg)
2. **Budget Constraint**: Total cost ≤ 75% of receipt price (profit margin ≤ 25%)
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
- **Quantity**: Calculated dynamically
- **Weight Formula**: `containerLength × density_kg_per_m × bars_per_container`
- **Selection Logic**:
  1. Look up `aluminum_bar_constants` table using `slatType` (e.g., "97mm" or "112mm")
  2. Try highest density first
  3. Check if inventory has enough (`final_quantity ≥ calculated_weight`)
  4. If insufficient, fall back to lower density option
- **Cost**: Uses `unitPrice` from "Nhôm_thanh_none" inventory item
- **Note**: Quantity in kg equals the calculated weight

## Phase 2: Variable Items Optimization

### Step 1: Group Items by Type
```python
itemsByType = {
    "steel_box": [...],
    "steel_i": [...],
    "steel_square": [...],
    "galvanized_sheet": [...]
}
```

### Step 2: Select Best Item from Each Type
For each item type:
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

### Step 3: Fill Remaining Weight
Iteratively fill remaining weight capacity:

1. **Sort all variable items** by weight-to-cost ratio (descending)
2. **For each item** (best ratio first):
   - Check if already selected (can add more quantity)
   - Calculate how much more can be added
   - Take maximum possible (respecting weight, budget, availability)
   - Update selected items
3. **Continue until**:
   - Weight reaches MAX_WEIGHT (3700kg), OR
   - Budget exhausted (cost ≥ maxCost), OR
   - No more items can be added

### Step 4: Iteration Loop
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
- Selected based on `slatType` (97mm or 112mm)

### 3. Steel Items (`unit = "kg"`)
```python
weight = quantity  # Quantity is already in kilograms
```
- Applies to: `steel_box`, `steel_i`, `steel_square`, `steel_u`, `steel_pipe`

### 4. Galvanized Sheets (`unit = "m"`)
```python
weight_per_meter = thickness_mm × width_mm × 7850 / 1,000,000
weight = quantity × weight_per_meter
```
- Dimensions extracted from item name using regex: `(\d+\.?\d*)\s*x\s*(\d+)`
- Example: "Tôn mạ kẽm 0.95 x 1200" → 0.95mm × 1200mm × 7850 / 1,000,000 = 8.9445 kg/m
- Density of galvanized steel: 7850 kg/m³

## Profit Margin Calculation

```python
totalCost = sum(item["quantity"] × item["unitPrice"] for all items)
profit = receiptPrice - totalCost
profitMargin = (profit / receiptPrice) × 100%
```

**Constraint**: `profitMargin ≤ 25%` (equivalent to `totalCost ≤ receiptPrice × 0.75`)

## Algorithm Pseudocode

```
function optimize(containerLength, itemModelType, slatType, receiptPrice):
    // Phase 1: Fixed Items
    walkingFloor = getWalkingFloor(itemModelType)  // 1 set
    aluminumWeight = calculateAluminumWeight(containerLength, slatType)
    aluminumItem = getAluminumItem(aluminumWeight)
    
    fixedWeight = walkingFloor.weight + aluminumWeight
    fixedCost = walkingFloor.cost + aluminumItem.cost
    maxCost = receiptPrice × 0.75  // 25% profit margin
    
    // Phase 2: Variable Items
    variableItems = getVariableItems()  // steel_box, steel_i, steel_square, galvanized_sheet
    selectedItems = []
    currentWeight = fixedWeight
    currentCost = fixedCost
    
    // Group by type for variety
    itemsByType = groupByType(variableItems)
    
    // Select best from each type
    for each type in itemsByType:
        bestItem = item with highest (weightPerUnit / unitPrice)
        maxQty = min(availableQty, weightSpaceLeft, budgetLeft)
        addItem(bestItem, maxQty)
    
    // Fill remaining weight
    sort all items by (weightPerUnit / unitPrice) descending
    
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
- `receiptPrice`: 600,000,000 VND

**Phase 1**:
- Walking floor: R2DX set (751 kg, 248,802,602 VND)
- Aluminum: 12.192 × 2.313 × 24 = 676.8 kg (83,540,339 VND)
- Fixed total: 1427.8 kg, 332,342,941 VND

**Phase 2**:
- Available budget: 450,000,000 - 332,342,941 = 117,657,059 VND
- Available weight: 3700 - 1427.8 = 2272.2 kg
- Select items by ratio:
  1. `thephop`: 1 kg / 16,640 VND = 0.0000601 ratio → 483 kg
  2. `THÉP_HỘP_KẼM`: 1 kg / 16,561 VND = 0.0000604 ratio → 249 kg
  3. `Tôn_mạ_kẽm_1.50x1250`: 14.72 kg / 236,364 VND = 0.0000623 ratio → 54 m (794.81 kg)
  4. Continue until weight/budget exhausted...

**Result**: ~3625 kg total weight, within 3000-3700 kg range

## Future Improvements

1. **Multi-objective Optimization**: Balance weight, cost, and variety more intelligently
2. **Backtracking**: Allow undoing selections if better combination found
3. **Multiple Solutions**: Generate top-N solutions for user to choose
4. **Weight Tolerance Configuration**: Make 3000-3700kg range configurable
5. **Item Priority Weights**: Allow certain items to be prioritized over others
6. **Caching**: Cache weight calculations for frequently used items

## References

- **Knapsack Problem**: https://en.wikipedia.org/wiki/Knapsack_problem
- **Greedy Algorithm**: https://en.wikipedia.org/wiki/Greedy_algorithm
- **Bin Packing Problem**: https://en.wikipedia.org/wiki/Bin_packing_problem

