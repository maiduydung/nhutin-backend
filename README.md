# NhuTin Backend

Azure Functions-based inventory data ingestion service for NhuTin. Processes Vietnamese warehouse reports from Google Drive and stores them in PostgreSQL.

## Features

- 📊 **Excel Ingestion** — Parses Vietnamese inventory reports (Tổng hợp tồn kho)
- 🔄 **Idempotent** — Safe to run multiple times, handles conflicts gracefully
- 🏷️ **Item Classification** — Auto-categorizes items (steel, fuel, equipment, etc.)
- 💰 **Price Tracking** — Records unit prices from import/export data
- ☁️ **Azure Ready** — Deployed as Azure Functions with PostgreSQL Flex

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure (copy and edit)
cp local.settings.json.example local.settings.json

# Run locally
func start

# Or test ingestion directly
python main.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/ingest` | Trigger inventory ingestion |

## Architecture

```
Google Drive → DriveFetcher → ItemNormalizer → PostgreSQL
     │              │               │              │
   Excel        Download        Classify       items
   Files        to /tmp         & Clean      inventory_records
                                             price_history
```

## Item Types

The normalizer auto-classifies items into types:

- `burning_fuel` — Bã điều, Dầu DO, Than, Trấu viên
- `hydraulic_pump` — Bơm thuỷ lực
- `walking_floor_*` — KMD, KSD, R2DX series (Keith Walking Floor)
- `steel_*` — Various steel types (box, pipe, plate, etc.)
- `aluminum`, `container`, `galvanized_sheet`, etc.

## Documentation

- [Agent Documentation](docs/agent.md) — Detailed technical docs
- [Changelog](CHANGELOG.md) — Version history

## Environment Variables

| Variable | Description |
|----------|-------------|
| `POSTGRES_*` | Database connection (USER, PASSWORD, HOST, PORT, DATABASE) |
| `GoogleServiceAccount` | Google API service account JSON |

## License

Private — NhuTin internal use only.
