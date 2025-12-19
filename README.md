# Nhu Tin BOM Optimizer

Azure Functions backend for optimizing container Bill of Materials (BOM) with profit margin targeting.

## What It Does

Given a container specification and receipt price, the optimizer:
1. **Hits target profit margin** (default 20%) by spending the right amount
2. **Maximizes weight** within container-length-based limits
3. **Always includes core items**: Walking floor, aluminum bars, hydraulic pump, hydraulic oil
4. **Builds containers from materials** when pre-built ones unavailable

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
│   ├── optimizer.py          # Main orchestrator
│   ├── fixed_items.py        # Core items (floor, pump, oil, aluminum)
│   ├── variable_filler.py    # Fill to budget with variable items
│   ├── container_builder.py  # Build container from materials
│   ├── weight_targets.py     # Length → weight interpolation
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

1. **Fixed items** are always included (walking floor, aluminum, pump, oil)
2. **Container** is either from inventory or built from materials
3. **Variable items** fill remaining budget to hit profit margin
4. Items prioritized by **weight-to-cost ratio** (max weight per VND)
