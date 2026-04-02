# CLAUDE.md -- LLM Context for Nhu Tin BOM Optimizer

## What is this project?

An Azure Functions API that generates optimized Bills of Materials (BOM) for truck body and container manufacturing. Given a container spec and receipt price, it outputs a parts list satisfying both weight (physics) and margin (accounting) constraints.

## Tech stack

- **Runtime:** Python 3.11, Azure Functions v4 (Flex Consumption)
- **Database:** PostgreSQL via psycopg2
- **Validation:** Pydantic v2
- **CI/CD:** GitHub Actions -> Azure OIDC deploy
- **No web framework** -- uses `azure.functions` HTTP bindings directly

## Architecture

The core is a 4-phase optimization pipeline in `services/optimizer.py`:

1. `feasibility_checker.py` -- Phase 0: derive weight/cost bounds, fail early if impossible
2. `fixed_items.py` -- Phase 1: add deterministic items (walking floor, pump, oil, aluminum bars)
3. `weight_filler.py` -- Phase 2: fill to minimum weight with structural materials
4. `margin_tuner.py` -- Phase 3: add expensive/light items to approach target profit margin
5. `micro_adjuster.py` -- Phase 4: swap cheap/heavy for expensive/light to fine-tune

**Golden Rule:** Never optimize margin before weight feasibility is locked.

## Key files

| File | Purpose |
|------|---------|
| `function_app.py` | HTTP endpoints (health check, process_receipt) |
| `config.py` | All constants: weight specs, container configs, hydraulic equipment |
| `models/user_input.py` | Pydantic model for request validation |
| `services/optimizer.py` | Main orchestrator class `OptimizerV2` |
| `services/container_builder.py` | Builds container BOM from raw materials (steel, sheets, consumables) |
| `services/database.py` | PostgreSQL wrapper for item pricing lookups |
| `services/inventory.py` | Parses Vietnamese inventory Excel files |
| `services/fetcher.py` | Google Drive API integration |
| `schema.psql` | Database schema |

## Domain context

- **Nhu Tin** is a Vietnamese logistics equipment manufacturer
- A "container" here is a truck body, not a shipping container
- Container types: `container_20ft`, `container_40ft` (pre-built), `mooc_long`, `thung_xe_tai` (built from materials)
- Walking floor models: R2DX, KSD, KMD (conveyor systems inside the truck body)
- All currency is VND (Vietnamese Dong), integers only
- Weight targets scale with container length: 6m=3500kg, 9m=4500kg, 12m=7000kg, 15m=8000kg

## Important patterns

- **camelCase** for Python variables and function parameters (project convention, not PEP 8)
- Config values come from `local.settings.json` (dev) or Azure App Settings (prod), loaded via `config.getConfig()`
- Item prices and weights come from PostgreSQL, not hardcoded
- The optimizer never mutates input -- each phase returns a new items list
- Error cases return `status: "error"` with diagnostic info, not HTTP error codes

## Running tests

```bash
pytest tests/test_optimizer_v2.py -v
pytest tests/test_consumables.py -v
```

Tests require a live PostgreSQL connection (configured via `local.settings.json`).

## Critical rule: always test before pushing

The `processReceipts` branch has CI/CD to production. **Never push without running the full test suite first.** Write tests for any new fix or feature, run `pytest tests/ -v`, and only push when all tests pass. This applies to all branches with deployment pipelines.
