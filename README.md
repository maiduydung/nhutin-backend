# Nhu Tin BOM Optimizer API

Azure Functions backend that generates optimized Bills of Materials (BOM) for truck body manufacturing. Given a container specification and receipt price, it produces a cost-optimized parts list that satisfies both physics (weight) and accounting (profit margin) constraints simultaneously.

Built for [Nhu Tin](https://nhutinvn.com), a Vietnamese logistics equipment manufacturer.

## The Problem

Generating a BOM for a truck body requires balancing two competing constraints:

- **Weight feasibility** -- the loaded truck must meet road-legal weight targets (varies by container length)
- **Profit margin** -- material costs must land within a target margin of the receipt price

These constraints often conflict: cheap materials are heavy, expensive materials are light. A naive margin-first approach frequently violates weight limits. This API solves both simultaneously.

## Algorithm: 4-Phase Constrained Feasibility

The optimizer uses a **feasibility-first** approach -- weight is locked before margin is tuned.

| Phase | Name | Purpose |
|-------|------|---------|
| 0 | **Feasibility Check** | Derive weight/cost bounds, fail early if constraints are impossible |
| 1 | **Fixed Items** | Add deterministic items: walking floor, aluminum bars, hydraulic pump, oil |
| 2 | **Weight Filling** | Reach minimum weight using structural materials (steel frame, galvanized sheets) |
| 3 | **Margin Tuning** | Add expensive/light items (aluminum, stainless steel) to hit target profit margin |
| 4 | **Micro-Adjust** | Swap cheap/heavy items for expensive/light ones to fine-tune within weight limits |

**Golden Rule:** Never optimize margin before weight feasibility is locked.

### Weight Targets (by Container Length)

| Length | Target Weight | Tolerance |
|--------|---------------|-----------|
| 6m | 3,500 kg | +/- 500 kg |
| 9m | 4,500 kg | +/- 500 kg |
| 12m | 7,000 kg | +/- 500 kg |
| 15m | 8,000 kg | +/- 500 kg |

Intermediate lengths are linearly interpolated.

## API

### `POST /api/process_receipt`

**Request:**

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

| Parameter | Type | Description |
|-----------|------|-------------|
| `containerType` | string | `container_20ft`, `container_40ft`, `mooc_long`, `thung_xe_tai` |
| `containerLength` | float | Length in meters |
| `itemModelType` | string | Walking floor model: `R2DX`, `KSD`, `KMD` |
| `slatType` | string | `97mm` or `112mm` |
| `thickness` | int | Aluminum bar thickness: `6` or `8` mm |
| `receiptPrice` | int | Receipt price in VND |
| `targetProfitMargin` | float | Target margin (0.05--0.50, default 0.20) |

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

### `GET /api/health`

Returns service status. No authentication required.

## Project Structure

```
function_app.py               # Azure Functions HTTP endpoints
config.py                     # Constants, weight specs, hydraulic config
models/
  user_input.py               # Pydantic request validation
services/
  optimizer.py                # Main orchestrator (4-phase algorithm)
  feasibility_checker.py      # Phase 0: Derive bounds, fail early
  fixed_items.py              # Phase 1: Deterministic core items
  weight_filler.py            # Phase 2: Fill to min weight with structural materials
  margin_tuner.py             # Phase 3: Add expensive items to hit margin
  micro_adjuster.py           # Phase 4: Swap cheap/heavy for expensive/light
  container_builder.py        # Build container from raw materials
  weight_calculator.py        # Item weight calculations
  database.py                 # PostgreSQL connection wrapper
  inventory.py                # Excel inventory parser
  fetcher.py                  # Google Drive file fetcher
  notify.py                   # Email notifications on errors
tests/
  test_optimizer_v2.py        # Unit tests for 4-phase algorithm
  test_consumables.py         # Consumables integration tests
  test_auto_fallback.py       # Auto-fallback mode tests
  test_runner.py              # Integration test runner (local + prod)
docs/
  ALGORITHM.md                # Detailed algorithm documentation
  RULES.md                    # Business rules and constraints
  UI_SCHEMA.md                # Frontend integration schema
```

## Tech Stack

- **Runtime:** Python 3.11, Azure Functions v4 (Flex Consumption)
- **Database:** PostgreSQL (Azure Database for PostgreSQL)
- **Validation:** Pydantic v2
- **CI/CD:** GitHub Actions with Azure OIDC authentication
- **Data:** pandas + openpyxl for inventory Excel parsing
- **Integrations:** Google Drive API (inventory sync), SMTP (error alerts)

## Running Locally

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp local.settings.json.example local.settings.json  # Add your credentials

# Run tests
pytest tests/test_optimizer_v2.py -v

# Start Azure Functions locally
func start
```

## Container Types

| Type | Pre-built Container | Notes |
|------|---------------------|-------|
| `container_20ft` | Yes | Uses pre-built container if available |
| `container_40ft` | Yes | Uses pre-built container if available |
| `mooc_long` | No | Always builds from raw materials |
| `thung_xe_tai` | No | Always builds from raw materials |

## License

Proprietary -- Nhu Tin Co., Ltd.
