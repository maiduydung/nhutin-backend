# Nhu Tin BOM Optimizer

Azure Functions backend for optimizing container Bill of Materials (BOM) with profit margin targeting.

## What It Does

Given a container specification and receipt price, the optimizer uses a **4-phase algorithm**:

1. **Phase 0 - Feasibility Check**: Derive bounds, fail early if impossible
2. **Phase 1 - Fixed Items**: Walking floor, aluminum bars, pump, oil (deterministic)
3. **Phase 2 - Weight Filling**: Reach minimum weight with structural materials
4. **Phase 3 - Margin Tuning**: Add expensive items to hit target margin
5. **Phase 4 - Micro-Adjust**: Swap cheap/heavy for expensive/light if needed

**Golden Rule**: Never optimize margin before weight feasibility is locked.

## Weight Targets (by Container Length)

| Length | Target Weight | Range (±500kg) |
|--------|---------------|----------------|
| 6m | 3,500 kg | 3,000-4,000 kg |
| 9m | 4,500 kg | 4,000-5,000 kg |
| 12m | 7,000 kg | 6,500-7,500 kg |
| 15m | 8,000 kg | 7,500-8,500 kg |

Intermediate lengths are linearly interpolated.

## API

### POST `/api/process_receipt`

```json
{
    "containerType": "mooc_long",
    "containerLength": 15.0,
    "itemModelType": "KSD",
    "slatType": "112mm",
    "thickness": 6,
    "receiptPrice": 700000000,
    "targetProfitMargin": 0.20
}
```

**Parameters:**
- `containerType`: `container_20ft`, `container_40ft`, `mooc_long`, `thung_xe_tai`
- `containerLength`: Length in meters
- `itemModelType`: `R2DX`, `KSD`, `KMD` (walking floor model)
- `slatType`: `97mm` or `112mm`
- `thickness`: `6` or `8` (aluminum bar thickness in mm)
- `receiptPrice`: Receipt price in VND
- `targetProfitMargin`: Target profit margin (0.05-0.50, default 0.20)

**Response:**
```json
{
    "status": "ok",
    "items": [...],
    "totalWeight": 7217.4,
    "totalCost": 559920731,
    "receiptPrice": 700000000,
    "profit": 140079269,
    "profitMargin": 20.01,
    "containerBuiltFromMaterials": true,
    "constraints": {...}
}
```

## Project Structure

```
├── function_app.py           # Azure Functions endpoints
├── config.py                 # Configuration & constants
├── models/
│   └── user_input.py         # Request validation
├── services/
│   ├── optimizer.py          # Main orchestrator (OptimizerV2)
│   ├── feasibility_checker.py # Phase 0: Bounds & validation
│   ├── fixed_items.py        # Phase 1: Core items
│   ├── weight_filler.py      # Phase 2: Fill to minWeight
│   ├── margin_tuner.py       # Phase 3: Tune cost to margin
│   ├── micro_adjuster.py     # Phase 4: Swap cheap↔expensive
│   ├── container_builder.py  # Build container from materials
│   ├── weight_calculator.py  # Item weight calculations
│   └── database.py           # PostgreSQL wrapper
└── tests/
    └── test_optimizer_v2.py  # Comprehensive tests
```

## Running Locally

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/test_optimizer_v2.py -v

# Start Azure Functions
func start
```

## Container Types

| Type | Container in BOM | Notes |
|------|------------------|-------|
| `container_20ft` | ✅ Yes | Uses pre-built if available |
| `container_40ft` | ✅ Yes | Uses pre-built if available |
| `mooc_long` | ❌ No | Always builds from materials |
| `thung_xe_tai` | ❌ No | Always builds from materials |

## How Optimization Works

1. **Phase 0**: Check if constraints are achievable (fail early if not)
2. **Phase 1**: Add fixed items (walking floor, aluminum, pump, oil, container)
3. **Phase 2**: Fill to minimum weight using structural materials (steel, sheets)
4. **Phase 3**: Add expensive items (aluminum, stainless) to hit margin target
5. **Phase 4**: Swap cheap/heavy items for expensive/light if at weight limit

**Key Insight**: Weight is locked first, then margin is optimized within weight constraints.
