# Container BOM Optimization Algorithm V2

## Problem Statement

Given a container specification and receipt price, optimize the Bill of Materials (BOM) to satisfy:

1. **Physics Constraint**: Total weight must be within a range based on container length
2. **Accounting Constraint**: Profit margin must be within a target range

These two constraints often conflict—the old algorithm optimized margin-first and hoped weight would align. This V2 algorithm fixes that with a **feasibility-first approach**.

## Golden Rule

> **Never optimize margin before weight feasibility is locked.**

## 4-Phase Algorithm

### Phase 0: Feasibility Check

Derive hard bounds BEFORE attempting optimization. Fail early if constraints are impossible.

```python
# Weight bounds (from container length)
targetWeight = interpolate(containerLength)  # 6m→3500, 9m→4500, 12m→7000, 15m→8000
minWeight = targetWeight - 500
maxWeight = targetWeight + 500

# Cost bounds (from receipt price and margin)
targetCost = receiptPrice × (1 - targetMargin)
maxCost = receiptPrice × (1 - minMargin)  # Maximum we can spend
minCost = receiptPrice × (1 - maxMargin)  # Minimum we must spend
```

**Early Failure Checks:**
- Fixed items exceed weight limit → impossible build
- Fixed items exceed budget → impossible margin
- Not enough materials to reach weight → insufficient inventory

### Phase 1: Fixed Items (Deterministic)

Always included, no optimization:

| Item | Selection Logic | Weight |
|------|-----------------|--------|
| Walking Floor | Based on `itemModelType` (R2DX/KSD/KMD) | 503-751 kg |
| Aluminum Bars | Formula: `length × density × bars` | ~650-850 kg |
| Hydraulic Pump | R2DX→130cc, Others→108cc | ~50 kg |
| Hydraulic Oil | 1 barrel (200L) | ~200 kg |

**Container Handling:**
- `container_20ft/40ft`: Use pre-built if available, else build from materials
- `mooc_long/thung_xe_tai`: Always build structure from raw materials

### Phase 2: Weight-First Filling

Fill materials to reach **minimum weight** using structural priority:

```python
PRIORITY_ORDER = [
    "steel_box",      # Structural frame
    "steel_u",        # Beams
    "steel_i",        # I-beams
    "galvanized_sheet",  # Walls/roof
    "stainless_steel",   # Accessories
    "aluminum",       # Additional weight
]

while totalWeight < minWeight:
    add next structural item (bounded by availability)
```

**Key Insight:** At the end of Phase 2, weight is guaranteed within window. Margin may be off—this is fine.

### Phase 3: Margin Tuning

Add expensive/light items to increase cost and hit target margin:

```python
# Sort items by cost-to-weight ratio (highest first)
sortedItems = sorted(items, key=lambda x: x.unitPrice / x.weightPerUnit, reverse=True)

while profitMargin > targetMargin:
    add item with highest cost-per-kg
    stop if totalWeight > maxWeight
```

**Best Items for Margin Tuning:**
- Aluminum: 123,000-132,000 VND/kg
- Stainless Steel: 45,000-50,000 VND/kg
- Zero-weight items (containers, rivets): Add cost without weight

### Phase 4: Micro-Adjust (Swap Optimization)

If we hit weight limit before reaching target cost, swap cheap/heavy items for expensive/light ones:

```python
while costGap > 1M and iterations < 50:
    find cheapest item by VND/kg in current selection
    find most expensive item by VND/kg in available inventory
    swap equal weight: remove cheap, add expensive
    # Result: same weight, higher cost
```

**Example:**
- Remove 100kg steel @ 15,000 VND/kg = 1.5M VND
- Add 100kg aluminum @ 123,000 VND/kg = 12.3M VND
- Net: +10.8M VND cost, 0kg weight change

## Weight Targets by Container Length

| Length | Target Weight | Min Weight | Max Weight |
|--------|---------------|------------|------------|
| 6m | 3,500 kg | 3,000 kg | 4,000 kg |
| 9m | 4,500 kg | 4,000 kg | 5,000 kg |
| 12m | 7,000 kg | 6,500 kg | 7,500 kg |
| 15m | 8,000 kg | 7,500 kg | 8,500 kg |

Intermediate lengths use linear interpolation.

## Margin Bounds

- **Target Margin**: User-specified (default 20%)
- **Max Margin**: Target margin + 0.5% tolerance
- **Min Margin**: Target margin - 5% (breathing room)

Example for 20% target:
- Acceptable range: 15% - 20.5%

## Why This Works

| Old Algorithm | New Algorithm (V2) |
|---------------|-------------------|
| Greedy on ratio | Feasibility → Tuning |
| Margin-driven | Weight-driven |
| Breaks silently | Fails loudly with explanation |
| Hard to explain | Tax/CFO explainable |

**Philosophy:**
> "First make it physically real, then make it financially optimal"

This matches how real logistics + accounting works.

## Service Architecture

```
services/
├── optimizer.py           # Main orchestrator (OptimizerV2)
├── feasibility_checker.py # Phase 0: Bounds & validation
├── fixed_items.py         # Phase 1: Core items
├── weight_filler.py       # Phase 2: Fill to minWeight
├── margin_tuner.py        # Phase 3: Tune cost to margin
├── micro_adjuster.py      # Phase 4: Swap cheap↔expensive
├── container_builder.py   # Build container from materials
├── weight_calculator.py   # Item weight calculations
└── database.py            # PostgreSQL wrapper
```

## Example Optimization

**Input:**
- Container: mooc_long, 15m
- Receipt: 700,000,000 VND
- Target Margin: 20%

**Phase 0 - Bounds:**
- Weight: 7,500-8,500 kg
- Cost: 560M-595M VND
- Margin: 15-20%

**Phase 1 - Fixed Items:**
- Walking floor (KSD): 503 kg, 157M VND
- Aluminum bars: 797 kg, 105M VND
- Hydraulic pump: 50 kg, 12M VND
- Hydraulic oil: 200 kg, 9M VND
- Container structure: 2,819 kg, 139M VND
- **Total: 4,368 kg, 422M VND**

**Phase 2 - Weight Filling:**
- Add steel box, U-steel, galvanized sheets
- **Total: 7,500 kg, 526M VND** ✅ Weight target achieved!

**Phase 3 - Margin Tuning:**
- Add rivets (zero-weight, low cost)
- **Total: 7,500 kg, 527M VND**

**Phase 4 - Micro-Adjust:**
- Swap 300kg steel → aluminum
- **Final: 7,500 kg, 559M VND, 20.1% margin** ✅ ✅

## Error Handling

The algorithm provides clear failure reasons:

```json
{
  "status": "error",
  "error": "Fixed items (349,909,234) exceed max budget (297,500,000)",
  "constraints": {
    "weightOk": true,
    "marginOk": false
  }
}
```

Common failure modes:
1. **Budget too low**: Fixed items alone exceed budget for target margin
2. **Inventory insufficient**: Not enough materials to reach weight target
3. **Conflicting constraints**: Weight limit reached before cost target (reported as warning, provides best-effort result)

## References

- [docs/comments.md](comments.md) - Original analysis and algorithm design
- [CHANGELOG.md](../CHANGELOG.md) - Version history
- [Knapsack Problem](https://en.wikipedia.org/wiki/Knapsack_problem) - Related optimization problem
