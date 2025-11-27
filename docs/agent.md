# Agent Documentation

## Project Overview

**NhuTin Backend** is an Azure Functions-based data ingestion service that processes Vietnamese inventory reports from Google Drive and stores them in PostgreSQL.

---

## Architecture

```
Google Drive (Excel Files)
        │
        ▼
┌──────────────────────┐
│    DriveFetcher      │  ← Authenticates via Service Account
│  (services/fetcher)  │  ← Downloads latest Excel to /tmp
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│     Inventory        │  ← Parses Vietnamese date formats
│ (services/inventory) │  ← Extracts item & record data
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│     PostgreSQL       │  ← items, inventory_records, price_history
│    (Azure Flex)      │
└──────────────────────┘
```

---

## Core Components

### 1. `function_app.py`
Azure Functions HTTP triggers:
- **GET /api/health** — Health check endpoint
- **POST /api/ingest** — Triggers inventory ingestion pipeline

### 2. `services/fetcher.py`
**Class: `DriveFetcher`**
- Authenticates with Google Drive using service account credentials
- Finds folders by name, lists files, downloads Excel files
- Always writes to `/tmp` (Azure Functions requirement)

### 3. `services/inventory.py`
**Class: `Inventory`**
- Parses Vietnamese date from Excel row 2: `Ngày DD tháng MM năm YYYY`
- Reads inventory data starting from row 6
- Uses `ItemNormalizer` to clean and classify items before insertion
- Upserts items and inventory_records to PostgreSQL
- Calculates and stores unit prices in price_history table

### 4. `services/normalizer.py`
**Class: `ItemNormalizer`**
- `normalizeCode()` — Cleans item codes (removes quotes, spaces → underscores)
- `normalizeName()` — Cleans item names (trims whitespace, removes quotes)
- `normalizeUnit()` — Standardizes units (kg, L, pcs, set, m)
- `classifyType()` — Classifies items into types based on code/name patterns
- `normalize()` — Returns a `NormalizedItem` dataclass with all cleaned data

**Item Types:**
| Type | Example Items |
|------|--------------|
| burning_fuel | Bã điều, Dầu DO, Than, Trấu viên |
| hydraulic_pump | Bơm thuỷ lực |
| controller | hộp điều khiển chế tạo |
| walking_floor_kmd | KMD series (Keith Walking Floor) |
| walking_floor_ksd | KSD series (Keith Walking Floor) |
| walking_floor_r2dx | R2DX series (also handles RIIDX typo) |
| walking_floor | Generic sàn di động (no model detected) |
| aluminum | Nhôm thanh |
| steel | General steel items |
| stainless_steel | Thép không gỉ |
| steel_box | Thép hộp |
| steel_pipe | Thép ống |
| steel_plate | Thép tấm |
| galvanized_sheet | Tôn mạ kẽm |
| container | Vỏ container |
| other | Unclassified items |

**Typo Handling:**
The normalizer handles common user input typos:
- `riidx`, `ridx`, `r2d` → `r2dx`
- `kds`, `skd` → `ksd`
- `kdm`, `mkd` → `kmd`

### 5. `services/database.py`
**Class: `Database`**
- `getDbConnection()` — Returns psycopg2 connection using credentials from `config.py`
- `initSchema()` — Initializes database tables using `schema.psql` (CREATE TABLE IF NOT EXISTS)
- Auto-finds schema file in project root or /tmp

### 6. `config.py`
Configuration loader with fallback chain:
1. `local.settings.json` → Values section
2. Environment variables
3. Default value

---

## Database Schema

### `items`
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| code | TEXT | Unique item code |
| name | TEXT | Item name |
| type | TEXT | Item classification (burning_fuel, steel, etc.) |
| unit | TEXT | Unit of measure |

### `inventory_records`
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| item_id | INTEGER | FK → items.id |
| record_date | DATE | Report date |
| initial_quantity | INTEGER | Opening stock |
| initial_value | BIGINT | Opening value |
| imported_quantity | INTEGER | Received qty |
| imported_value | BIGINT | Received value |
| exported_quantity | INTEGER | Issued qty |
| exported_value | BIGINT | Issued value |
| final_quantity | INTEGER | Closing stock |
| final_value | BIGINT | Closing value |

### `price_history`
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| item_id | INTEGER | FK → items.id |
| price | NUMERIC | Unit price |
| source | TEXT | Price source (e.g., "import", "export") |
| note | TEXT | Additional notes |
| effective_at | TIMESTAMP | When price was recorded |

---

## Data Flow

1. **Trigger**: HTTP POST to `/api/ingest`
2. **Fetch**: Download latest Excel from "Nhu Tin" folder
3. **Init Schema**: `CREATE TABLE IF NOT EXISTS` (safe to run multiple times)
4. **Parse**: Extract date from row 2, data from row 6+
5. **Normalize**: Clean codes/names, classify item types, apply default units
6. **Upsert**: Insert/update items → inventory_records → price_history
7. **Respond**: Return success/error JSON

### Conflict Handling (Idempotent)

| Table | Unique Key | Behavior |
|-------|-----------|----------|
| `items` | `code` | Updates name, type, unit |
| `inventory_records` | `(item_id, record_date)` | Updates all values |
| `price_history` | `(item_id, source, effective_at)` | Skips duplicates |

---

## Excel File Structure

```
Row 1: Title
Row 2: "Ngày DD tháng MM năm YYYY" (date)
Row 3-5: Headers
Row 6+: Data
  Col B (1): Item code
  Col C (2): Item name
  Col D (3): Unit
  Col E-F (4-5): Initial qty/value
  Col G-H (6-7): Imported qty/value
  Col I-J (8-9): Exported qty/value
  Col K-L (10-11): Final qty/value
```

---

## Configuration

### Required Environment Variables
| Variable | Description |
|----------|-------------|
| POSTGRES_USER | Database username |
| POSTGRES_PASSWORD | Database password |
| POSTGRES_HOST | Database host |
| POSTGRES_PORT | Database port |
| POSTGRES_DATABASE | Database name |
| GoogleServiceAccount | Google API service account JSON |

---

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run main script
python main.py

# Run as Azure Function
func start
```

---

## Testing Individual Modules

```bash
# Test database connection & schema init
python -m services.database

# Test fetcher (Google Drive)
python -m services.fetcher

# Test normalizer (shows classification examples)
python -m services.normalizer

# Test inventory ingestion
python -m services.inventory

# Run full pipeline
python main.py
```

