# NhuTin Backend

Azure Functions-based inventory data ingestion service for NhuTin. Processes Vietnamese warehouse reports from Google Drive and stores them in PostgreSQL with automatic item classification, price tracking, and snapshot-based ingestion (MVP: wipes database before each ingestion).

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Core Components](#core-components)
- [Database Schema](#database-schema)
- [Data Flow](#data-flow)
- [Excel File Structure](#excel-file-structure)
- [Item Classification System](#item-classification-system)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)

---

## Overview

**NhuTin Backend** is a serverless data ingestion pipeline that:

- 📊 **Fetches Excel files** from Google Drive ("Nhu Tin" folder)
- 🔄 **Parses Vietnamese inventory reports** with date extraction from row 2
- 🏷️ **Auto-classifies items** into types (steel, fuel, equipment, etc.) with typo handling
- 💰 **Tracks unit prices** from import/export transactions
- 🗄️ **Stores data** in PostgreSQL with snapshot-based ingestion (MVP)
- ☁️ **Deploys as Azure Functions** with HTTP triggers

### Key Features

- **Snapshot-Based Ingestion (MVP)**: Wipes database before each ingestion to match Excel snapshot exactly. Ensures deleted items from accounting software are also removed. All operations wrapped in transaction for safety.
- **Intelligent Normalization**: Cleans messy user input, fixes typos, standardizes units
- **Price History Tracking**: Automatically calculates and stores unit prices from import/export data
- **Vietnamese Language Support**: Parses Vietnamese date formats and item names
- **Azure-Native**: Designed for Azure Functions with `/tmp` file handling

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Google Drive                             │
│              "Nhu Tin" folder (Excel files)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              DriveFetcher (services/fetcher.py)             │
│  • Authenticates via Google Service Account                 │
│  • Finds folder by name ("Nhu Tin")                         │
│  • Lists Excel files sorted by modifiedTime                │
│  • Downloads latest file to /tmp (Azure Functions)          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│            Inventory (services/inventory.py)                 │
│  • Extracts date from row 2 (Vietnamese format)            │
│  • Reads data starting from row 6                           │
│  • Parses columns: code, name, unit, quantities, values      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│        ItemNormalizer (services/normalizer.py)              │
│  • Normalizes codes (removes quotes, spaces → underscores)  │
│  • Normalizes names (trims whitespace, removes quotes)       │
│  • Normalizes units (kg, L, pcs, set, m)                    │
│  • Classifies item types based on code/name patterns        │
│  • Handles typos (riidx → r2dx, kds → ksd, etc.)           │
│  • Applies default units for certain item types             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL (Azure Database)                     │
│  • items (code, name, type, unit)                           │
│  • inventory_records (quantities & values per date)          │
│  • price_history (unit prices from import/export)           │
└─────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

1. **HTTP Request** → `function_app.py` receives POST to `/api/ingest`
2. **File Fetching** → `DriveFetcher.fetchLatestExcelFromFolder("Nhu Tin")` downloads latest Excel
3. **Schema Initialization** → `Database.initSchema()` ensures tables exist (idempotent)
4. **Data Parsing** → `Inventory.ingestInventoryFromExcel()` extracts date and data
5. **Normalization** → `ItemNormalizer.normalize()` cleans and classifies each item
6. **Database Upsert** → Items → inventory_records → price_history (with conflict handling)
7. **Response** → Returns JSON with status and file path

---

## Core Components

### 1. `function_app.py` - Azure Functions HTTP Triggers

**Purpose**: Entry point for Azure Functions HTTP requests.

**Endpoints**:
- **GET `/api/health`**: Health check endpoint
  - Returns: `{"status": "ok", "message": "NhuTin DB Ingestion Service is running"}`
  - Status: 200
  
- **POST `/api/ingest`**: Triggers inventory ingestion pipeline
  - Returns: `{"status": "ok", "filePath": "/tmp/filename.xlsx"}` on success
  - Returns: `{"status": "error", "message": "..."}` on failure
  - Status: 200 on success, 500 on error

**Authentication**: Function-level auth (`http_auth_level=func.AuthLevel.FUNCTION`)

**Error Handling**: Catches exceptions, logs errors, returns JSON error responses

---

### 2. `services/fetcher.py` - Google Drive File Fetcher

**Class**: `DriveFetcher`

**Purpose**: Authenticates with Google Drive API and downloads Excel files.

**Key Methods**:

- `__init__(settingsFile: str = "local.settings.json", scopes: list[str] | None = None)`
  - Loads Google Service Account credentials from:
    1. `local.settings.json` → top-level `GoogleServiceAccount` key
    2. `local.settings.json` → `Values.GoogleServiceAccount` (dict or JSON string)
    3. Environment variables: `GOOGLE_SERVICE_ACCOUNT` or `GoogleServiceAccount`
  - Builds Google Drive API client with read-only scope

- `findFolderByName(folderName: str, parentId: str | None = None)`
  - Searches for folder by name using Drive API query
  - Returns: `{"id": "...", "name": "..."}` or `None`

- `listFilesInFolder(folderId: str, mimeType: str | None = None)`
  - Lists files in folder, optionally filtered by MIME type
  - Sorted by `modifiedTime desc`
  - Returns: List of file dicts with `id`, `name`, `mimeType`, `modifiedTime`

- `downloadFile(fileId: str, destinationPath: str)`
  - Downloads file from Drive to local path
  - Creates parent directories if needed
  - Shows download progress

- `fetchLatestExcelFromFolder(folderName: str, destinationPath: str | None = None)`
  - Finds folder by name
  - Lists Excel files (`.xlsx` and `.xls` MIME types)
  - Sorts by `modifiedTime`, selects latest
  - Downloads to `/tmp/filename.xlsx` (Azure Functions requirement)
  - Returns: File path or `None` if not found

**Important Notes**:
- Always writes to `/tmp` directory (Azure Functions writable location)
- Handles both `.xlsx` and `.xls` file formats
- Uses service account authentication (no user interaction)

---

### 3. `services/inventory.py` - Inventory Data Ingestion

**Class**: `Inventory`

**Purpose**: Parses Excel files and ingests inventory data into PostgreSQL.

**Key Methods**:

- `_extractDateFromVietnameseFormat(dateString: str) -> datetime`
  - Parses Vietnamese date format: `"Ngày DD tháng MM năm YYYY"`
  - Uses regex pattern: `r'Ngày\s+(\d+)\s+tháng\s+(\d+)\s+năm\s+(\d+)'`
  - Returns: `datetime` object or current date on parse failure

- `_calculateUnitPrice(value: int, quantity: int) -> Decimal | None`
  - Calculates unit price: `value / quantity`
  - Returns: `Decimal` if both > 0, `None` otherwise

- `_insertPriceHistory(cursor, itemId: int, price: Decimal, source: str, effectiveAt: datetime)`
  - Inserts price record into `price_history` table
  - Uses `ON CONFLICT DO NOTHING` to avoid duplicates
  - Source values: `"import"` or `"export"`
  - **SQL**: `INSERT INTO price_history (item_id, price, source, effective_at) VALUES (...) ON CONFLICT DO NOTHING`
  - **Note**: PostgreSQL infers conflict target from unique constraint `(item_id, source, effective_at)`

- `_wipeDatabase(cursor)`
  - **MVP snapshot behavior**: Wipes all existing data before ingestion
  - Deletes in order: `price_history` → `inventory_records` → `items` (respects foreign key constraints)
  - Ensures database matches Excel snapshot exactly (removes deleted items)
  - Called automatically at start of ingestion within transaction

- `ingestInventoryFromExcel(filePath: str)`
  - **Main ingestion method**
  - **MVP Behavior**: Wipes existing database data before ingesting fresh snapshot
  - Initializes schema via `Database.initSchema()` (idempotent)
  - Wipes all existing data via `_wipeDatabase()` (within transaction)
  - Reads row 2 (index 1) to extract date string
  - Reads data starting from row 6 (skiprows=5)
  - Column mapping:
    - Column B (1): `code`
    - Column C (2): `name`
    - Column D (3): `unit`
    - Columns E-F (4-5): `initial_quantity`, `initial_value`
    - Columns G-H (6-7): `imported_quantity`, `imported_value`
    - Columns I-J (8-9): `exported_quantity`, `exported_value`
    - Columns K-L (10-11): `final_quantity`, `final_value`
  - For each row:
    1. Skips rows with missing `code` or `name`
    2. Normalizes item via `ItemNormalizer.normalize()`
    3. Upserts `items` table (ON CONFLICT updates name/type/unit)
    4. Upserts `inventory_records` table (ON CONFLICT updates all values)
    5. Calculates and inserts price history from import/export data
  - Commits transaction on success, rolls back on error
  - Logs number of price records inserted

**Transaction Handling**: Uses database transactions with commit/rollback

---

### 4. `services/normalizer.py` - Item Normalization and Classification

**Class**: `ItemNormalizer`

**Purpose**: Cleans and classifies inventory items from messy user input.

**Data Class**: `NormalizedItem`
```python
@dataclass
class NormalizedItem:
    code: str          # Normalized item code
    name: str          # Normalized item name
    itemType: str      # Classified item type
    unit: str | None   # Normalized unit (or None)
```

**Key Methods**:

- `normalizeCode(code: str) -> str`
  - Strips whitespace
  - Removes quotes (single, double, smart quotes)
  - Replaces spaces and multiple underscores with single underscore
  - Removes leading/trailing underscores
  - Example: `"  'ABC 123'  "` → `"ABC_123"`

- `normalizeName(name: str) -> str`
  - Normalizes whitespace (multiple spaces → single space)
  - Removes leading/trailing quotes (including smart quotes)
  - Example: `"  Item   Name  "` → `"Item Name"`

- `normalizeUnit(unit: str | None) -> str | None`
  - Normalizes unit to standard format
  - Unit mapping:
    - `kg`, `kilo`, `kilogram` → `kg`
    - `lít`, `lit`, `liter`, `litre`, `l` → `L`
    - `cái`, `cai`, `chiếc`, `chiec`, `pcs`, `piece` → `pcs`
    - `bộ`, `bo`, `set` → `set`
    - `mét`, `met`, `meter`, `m` → `m`
  - Returns `None` for null-like values (`NULL`, `NONE`, `N/A`, `NA`, `-`, `""`)

- `classifyType(code: str, name: str) -> str`
  - Classifies item type based on code and name patterns
  - **Typo Fixing**: Applies typo fixes before classification:
    - `riidx`, `r2d`, `rdx`, `r2xd`, `ridx`, `riix`, `r11dx` → `r2dx`
    - `kds`, `skd` → `ksd`
    - `kdm`, `mkd` → `kmd`
  - **Pattern Matching**: Checks patterns in order (first match wins)
  - Returns: Item type string or `"other"` if no match

- `normalize(code: str, name: str, unit: str | None) -> NormalizedItem`
  - **Main normalization method**
  - Normalizes code, name, unit
  - Classifies item type
  - Applies default units for certain types if unit is missing:
    - `walking_floor*`: `"set"`
    - `container`: `"set"`
    - `controller`: `"set"`
    - `hydraulic_pump`: `"pcs"`
  - Returns: `NormalizedItem` dataclass

**Item Type Classification Rules** (in order of precedence):

1. **Walking Floor Models** (checked first, most specific):
   - `walking_floor_ksd`: Matches `ksd`, `kds`, `skd`
   - `walking_floor_kmd`: Matches `kmd`, `kdm`, `mkd`
   - `walking_floor_r2dx`: Matches `r2dx`, `riidx`, `r2d`, `rdx`, `ridx`, `riix`, `r11dx`

2. **Burning Fuels**:
   - `burning_fuel`: Matches `badieu`, `bã điều`, `dau`, `dầu do`, `than`, `trauvien`, `trấu viên`

3. **Hydraulic/Engine Oil** (checked before hydraulic_pump):
   - `hydraulic_oil`: Matches `nhớt`, `hydraulic.*oil`, `engine.*oil`, `lubricant`

4. **Hydraulic Equipment**:
   - `hydraulic_pump`: Matches `bơm.*thuỷ.*lực`, `hydraulic.*pump`

5. **Controllers**:
   - `controller`: Matches `hộp.*điều.*khiển`, `controller`

6. **Walking Floor Generic**:
   - `walking_floor`: Matches `sàn.*di.*động`, `walking.*floor`, `keith`

7. **Aluminum**:
   - `aluminum`: Matches `nhôm`, `aluminum`, `aluminium`

8. **Steel Types** (specific before general):
   - `stainless_steel`: Matches `thép.*không.*gỉ`, `stainless`
   - `steel_box`: Matches `thép.*hộp`, `thep.*hop`
   - `steel_pipe`: Matches `thép.*ống`, `thep.*ong`
   - `steel_plate`: Matches `thép.*tấm`, `thep.*tam`
   - `steel_square`: Matches `thép.*vuông`, `thep.*vuong`
   - `steel_u`: Matches `thép.*u\d`, `thepu`, `thép u`
   - `steel_i`: Matches `thép.*i\d`, `thepi`
   - `steel`: Matches `thep`, `thép` (fallback)

9. **Galvanized Sheet**:
   - `galvanized_sheet`: Matches `tôn.*mạ.*kẽm`, `galvanized`

10. **Containers**:
    - `container`: Matches `vỏ.*container`, `container`

11. **Other**:
    - `other`: Default fallback for unclassified items

**Pattern Matching Notes**:
- Patterns are case-insensitive
- Patterns match against combined `code name` string (no anchors)
- Vietnamese diacritics handled via regex patterns
- Order matters: first match wins

---

### 5. `services/database.py` - Database Connection and Schema Management

**Class**: `Database`

**Purpose**: Manages PostgreSQL connections and schema initialization.

**Key Methods**:

- `getDbConnection() -> psycopg2.connection`
  - Creates new PostgreSQL connection using credentials from `config.py`
  - Connection parameters: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DATABASE`
  - Returns: `psycopg2.connection` object

- `initSchema() -> bool`
  - Initializes database schema by executing `schema.psql`
  - **Idempotent**: Uses `CREATE TABLE IF NOT EXISTS` (safe to run multiple times)
  - Finds schema file in order:
    1. Current directory: `schema.psql`
    2. Project root: `../schema.psql` (relative to services/)
    3. Azure Functions temp: `/tmp/schema.psql`
  - Returns: `True` on success, `False` if schema file not found
  - Logs success/failure

- `_findSchemaFile() -> str | None`
  - Private method to locate `schema.psql` file
  - Checks multiple locations (see above)
  - Returns: File path or `None`

**Schema File**: `schema.psql` (see [Database Schema](#database-schema) section)

---

### 6. `config.py` - Configuration Management

**Purpose**: Centralized configuration loader with fallback chain.

**Configuration Priority** (highest to lowest):

1. **`local.settings.json`** → `Values` section
2. **Environment variables** (via `os.getenv()`)
3. **Default value** (if provided)

**Key Configuration Variables**:

- `POSTGRES_USER`: Database username
- `POSTGRES_PASSWORD`: Database password
- `POSTGRES_HOST`: Database hostname
- `POSTGRES_PORT`: Database port (default: `5432`)
- `POSTGRES_DATABASE`: Database name
- `FORM_RECOGNIZER_ENDPOINT`: Azure Form Recognizer endpoint (optional)
- `FORM_RECOGNIZER_KEY`: Azure Form Recognizer key (optional)
- `GoogleServiceAccount`: Google Service Account JSON (dict or JSON string)

**Helper Function**: `get_config(key, default=None)`
- Checks `local.settings.json` → environment variables → default
- Returns: Configuration value or `None`

**Logging**: Configures basic logging with INFO level, formatted timestamps

**Azure Key Vault**: Code exists but commented out (can be enabled for production)

---

### 7. `main.py` - Local Testing Script

**Purpose**: Simple script to test ingestion pipeline locally.

**Usage**:
```bash
python main.py
```

**Flow**:
1. Creates `DriveFetcher` instance
2. Creates `Inventory` instance
3. Fetches latest Excel from "Nhu Tin" folder
4. Ingests inventory data

**Note**: Useful for local development and testing without Azure Functions runtime

---

## Database Schema

The database schema is defined in `schema.psql` and automatically initialized via `Database.initSchema()` on first ingestion. The schema uses `CREATE TABLE IF NOT EXISTS` for idempotent initialization.

### Schema File: `schema.psql`

**Location**: Project root (`schema.psql`)

**Initialization**: Automatically called by `Database.initSchema()` before ingestion, or can be run manually via `python -m services.database`

**Idempotency**: Safe to run multiple times (uses `CREATE TABLE IF NOT EXISTS`)

The schema file contains three tables with the following relationships:
- `items` ← `inventory_records` (one-to-many via `item_id` FOREIGN KEY)
- `items` ← `price_history` (one-to-many via `item_id` FOREIGN KEY)

**Foreign Key Behavior**: 
- Foreign keys use `REFERENCES items(id)` without explicit `ON DELETE` clause
- Default behavior: Prevents deletion of items that have related records
- To delete an item, you must first delete all related `inventory_records` and `price_history` records

All tables use `SERIAL` primary keys and include appropriate foreign key constraints and unique constraints for data integrity.

---

### `items` Table

Stores normalized item master data.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-incrementing item ID |
| `code` | TEXT | UNIQUE, NOT NULL | Normalized item code (unique identifier) |
| `name` | TEXT | NOT NULL | Normalized item name |
| `type` | TEXT | NOT NULL | Item classification type (see [Item Classification System](#item-classification-system)) |
| `unit` | TEXT | NULL | Unit of measure (kg, L, pcs, set, m, etc.) |

**Constraints**:
- PRIMARY KEY: `id` (SERIAL, auto-incrementing)
- UNIQUE: `code` (prevents duplicate items)
- NOT NULL: `code`, `name`, `type`

**Upsert Behavior**: `ON CONFLICT (code) DO UPDATE` updates `name`, `type`, `unit`

**SQL Definition**:
```sql
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    unit TEXT
);
```

---

### `inventory_records` Table

Stores daily inventory snapshots with quantities and values.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-incrementing record ID |
| `item_id` | INTEGER | NOT NULL, FK → items.id | Foreign key to items table |
| `record_date` | DATE | NOT NULL, DEFAULT CURRENT_DATE | Date of inventory record |
| `initial_quantity` | INTEGER | NULL | Opening stock quantity |
| `initial_value` | BIGINT | NULL | Opening stock value (in VND) |
| `imported_quantity` | INTEGER | NULL | Received quantity during period |
| `imported_value` | BIGINT | NULL | Received value (in VND) |
| `exported_quantity` | INTEGER | NULL | Issued quantity during period |
| `exported_value` | BIGINT | NULL | Issued value (in VND) |
| `final_quantity` | INTEGER | NULL | Closing stock quantity |
| `final_value` | BIGINT | NULL | Closing stock value (in VND) |

**Constraints**:
- PRIMARY KEY: `id` (SERIAL, auto-incrementing)
- FOREIGN KEY: `item_id` → `items.id` (CASCADE on delete)
- UNIQUE: `(item_id, record_date)` (one record per item per date)
- NOT NULL: `item_id`
- DEFAULT: `record_date` = `CURRENT_DATE`

**Upsert Behavior**: `ON CONFLICT (item_id, record_date) DO UPDATE` updates all quantity/value fields

**Note**: Values stored as BIGINT to handle large Vietnamese Dong amounts

**SQL Definition**:
```sql
CREATE TABLE IF NOT EXISTS inventory_records (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id),
    record_date DATE DEFAULT CURRENT_DATE,
    initial_quantity INTEGER,
    initial_value BIGINT,
    imported_quantity INTEGER,
    imported_value BIGINT,
    exported_quantity INTEGER,
    exported_value BIGINT,
    final_quantity INTEGER,
    final_value BIGINT,
    UNIQUE (item_id, record_date)
);
```

---

### `price_history` Table

Tracks unit prices over time from import/export transactions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-incrementing price record ID |
| `item_id` | INTEGER | NOT NULL, FK → items.id | Foreign key to items table |
| `price` | NUMERIC | NOT NULL | Unit price at that moment |
| `source` | TEXT | NULL | Price source: `"import"` or `"export"` |
| `note` | TEXT | NULL | Additional notes (optional) |
| `effective_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | When price was recorded |

**Constraints**:
- PRIMARY KEY: `id` (SERIAL, auto-incrementing)
- FOREIGN KEY: `item_id` → `items.id` (CASCADE on delete)
- UNIQUE: `(item_id, source, effective_at)` (prevents duplicate price records)
- NOT NULL: `item_id`, `price`, `effective_at`
- DEFAULT: `effective_at` = `NOW()`

**Upsert Behavior**: `ON CONFLICT DO NOTHING` (skips duplicates)

**Price Calculation**: `price = value / quantity` (calculated from `inventory_records`)

**Important Notes**:
- Prices stored as NUMERIC for precision (handles decimal values)
- `source` column is nullable (TEXT without NOT NULL constraint)
- In PostgreSQL, NULL values are considered distinct in unique constraints, so multiple NULL `source` values are allowed for the same `item_id` and `effective_at`
- The unique constraint prevents duplicate records with the same `(item_id, source, effective_at)` combination
- When `source` is NULL, PostgreSQL treats each NULL as distinct, allowing multiple price records with NULL source for the same item and timestamp

**SQL Definition**:
```sql
CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id),
    price NUMERIC NOT NULL,
    source TEXT,
    note TEXT,
    effective_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (item_id, source, effective_at)
);
```

---

## Data Flow

### Complete Ingestion Pipeline

1. **HTTP Request** → `POST /api/ingest`
2. **Authentication** → Azure Functions validates request (function-level auth)
3. **File Fetching**:
   - `DriveFetcher` authenticates with Google Service Account
   - Searches for "Nhu Tin" folder by name
   - Lists Excel files (`.xlsx`, `.xls`) sorted by `modifiedTime desc`
   - Downloads latest file to `/tmp/filename.xlsx`
4. **Schema Initialization**:
   - `Database.initSchema()` executes `schema.psql`
   - Creates tables if they don't exist (idempotent)
5. **Database Wipe (MVP Snapshot Behavior)**:
   - `Inventory._wipeDatabase()` deletes all existing data
   - Deletes in order: `price_history` → `inventory_records` → `items`
   - Ensures database matches Excel snapshot exactly (removes deleted items)
   - All operations within transaction (rollback on failure)
6. **Date Extraction**:
   - Reads row 2 (index 1) from Excel
   - Parses Vietnamese date: `"Ngày DD tháng MM năm YYYY"`
   - Converts to `datetime` object
7. **Data Parsing**:
   - Reads data starting from row 6 (skiprows=5)
   - Maps columns: code, name, unit, quantities, values
8. **For Each Row**:
   - **Skip** if `code` or `name` is missing
   - **Normalize**:
     - Clean code (remove quotes, spaces → underscores)
     - Clean name (trim whitespace, remove quotes)
     - Normalize unit (standardize format)
     - Classify type (pattern matching with typo handling)
     - Apply default unit if missing (for certain types)
   - **Upsert Items**:
     - `INSERT INTO items ... ON CONFLICT (code) DO UPDATE`
     - Returns `item_id`
   - **Upsert Inventory Records**:
     - `INSERT INTO inventory_records ... ON CONFLICT (item_id, record_date) DO UPDATE`
   - **Calculate Prices**:
     - Import price: `imported_value / imported_quantity` (if both > 0)
     - Export price: `exported_value / exported_quantity` (if both > 0)
   - **Insert Price History**:
     - `INSERT INTO price_history (item_id, price, source, effective_at) ... ON CONFLICT DO NOTHING`
     - Note: Uses `ON CONFLICT DO NOTHING` without explicit conflict target; PostgreSQL infers from unique constraint `(item_id, source, effective_at)`
9. **Transaction Commit**:
   - Commits all changes on success (wipe + ingestion)
   - Rolls back on any error (restores previous database state)
10. **Response**:
   - Returns JSON: `{"status": "ok", "filePath": "/tmp/..."}`

### Snapshot Behavior (MVP)

**Current Implementation**: Database is wiped before each ingestion to match Excel snapshot exactly.

| Step | Operation | Description |
|------|-----------|-------------|
| 1 | Wipe Database | Deletes all `price_history`, `inventory_records`, and `items` |
| 2 | Ingest Fresh Data | Inserts all items from Excel file |
| 3 | Transaction Safety | All operations in single transaction (rollback on failure) |

**Benefits**:
- Database always matches Excel snapshot exactly
- Deleted items from accounting software are automatically removed
- No orphaned or stale data
- Transaction safety ensures data integrity

**Note**: `ON CONFLICT` clauses in INSERT statements remain for safety but are redundant after wipe (no conflicts possible).

---

## Excel File Structure

### Expected Format

The service expects Vietnamese inventory reports with the following structure:

```
Row 1:  [Title/Header] (ignored)
Row 2:  [Date String] "Ngày DD tháng MM năm YYYY" (e.g., "Ngày 27 tháng 11 năm 2024")
Row 3:  [Column Headers] (ignored)
Row 4:  [Column Headers] (ignored)
Row 5:  [Column Headers] (ignored)
Row 6+: [Data Rows]
```

### Column Mapping (Row 6+)

| Excel Column | Index | Field Name | Description |
|--------------|-------|------------|-------------|
| A | 0 | (ignored) | Row number or other metadata |
| B | 1 | `code` | Item code |
| C | 2 | `name` | Item name |
| D | 3 | `unit` | Unit of measure |
| E | 4 | `initial_quantity` | Opening stock quantity |
| F | 5 | `initial_value` | Opening stock value (VND) |
| G | 6 | `imported_quantity` | Received quantity |
| H | 7 | `imported_value` | Received value (VND) |
| I | 8 | `exported_quantity` | Issued quantity |
| J | 9 | `exported_value` | Issued value (VND) |
| K | 10 | `final_quantity` | Closing stock quantity |
| L | 11 | `final_value` | Closing stock value (VND) |

### Date Parsing

- **Format**: `"Ngày DD tháng MM năm YYYY"`
- **Example**: `"Ngày 27 tháng 11 năm 2024"` → `datetime(2024, 11, 27)`
- **Regex Pattern**: `r'Ngày\s+(\d+)\s+tháng\s+(\d+)\s+năm\s+(\d+)'`
- **Fallback**: Uses current date if parsing fails

### Data Validation

- **Required Fields**: `code` and `name` (rows without both are skipped)
- **Optional Fields**: `unit`, quantities, values (can be NULL/empty)
- **Numeric Handling**: Converts to integers (0 if NULL/empty)
- **Value Storage**: Stored as BIGINT (handles large VND amounts)

---

## Item Classification System

### Classification Process

1. **Typo Fixing**: Applies typo corrections to code and name
2. **Pattern Matching**: Checks patterns in order (first match wins)
3. **Default Units**: Applies default units for certain types if missing

### Supported Item Types

| Type | Description | Examples | Default Unit |
|------|-------------|----------|--------------|
| `burning_fuel` | Fuel for burning/energy | Bã điều, Dầu DO, Than, Trấu viên | None |
| `hydraulic_oil` | Lubricants and oils | Nhớt Hydraulic Oil, Engine Oil, Lubricant | `can` |
| `hydraulic_pump` | Hydraulic pumps | Bơm thuỷ lực | `pcs` |
| `controller` | Control boxes | hộp điều khiển chế tạo | `set` |
| `walking_floor_ksd` | Keith Walking Floor KSD series | KSD 4.25, Sàn di động KSD | `set` |
| `walking_floor_kmd` | Keith Walking Floor KMD series | KMD300 24X97MM | `set` |
| `walking_floor_r2dx` | Keith Walking Floor R2DX series | R2DX 4.0, RIIDX (typo) | `set` |
| `walking_floor` | Generic walking floor (no model) | Sàn di động (generic) | `set` |
| `aluminum` | Aluminum items | Nhôm thanh | None |
| `steel` | General steel items | Thép (generic) | None |
| `stainless_steel` | Stainless steel | Thép không gỉ | None |
| `steel_box` | Steel boxes | Thép hộp | None |
| `steel_pipe` | Steel pipes | Thép ống | None |
| `steel_plate` | Steel plates | Thép tấm | None |
| `steel_square` | Square steel | Thép vuông | None |
| `steel_u` | U-shaped steel | Thép U | None |
| `steel_i` | I-beam steel | Thép I | None |
| `galvanized_sheet` | Galvanized sheets | Tôn mạ kẽm | None |
| `container` | Containers | Vỏ container | `set` |
| `other` | Unclassified items | (fallback) | None |

### Typo Handling

The normalizer automatically fixes common user input typos:

| Typo | Corrected To | Example |
|------|--------------|---------|
| `riidx`, `ridx`, `r2d`, `rdx`, `r2xd`, `riix`, `r11dx` | `r2dx` | `RIIDX_test` → classified as `walking_floor_r2dx` |
| `kds`, `skd` | `ksd` | `kds_test` → classified as `walking_floor_ksd` |
| `kdm`, `mkd` | `kmd` | `kdm_test` → classified as `walking_floor_kmd` |

### Unit Normalization

Units are normalized to standard formats:

| Input | Normalized | Examples |
|-------|------------|----------|
| `kg`, `kilo`, `kilogram` | `kg` | Weight measurements |
| `lít`, `lit`, `liter`, `litre`, `l` | `L` | Volume measurements |
| `cái`, `cai`, `chiếc`, `chiec`, `pcs`, `piece` | `pcs` | Piece counts |
| `bộ`, `bo`, `set` | `set` | Sets/assemblies |
| `mét`, `met`, `meter`, `m` | `m` | Length measurements |
| `phuy`, `thùng`, `thung`, `can` | `can` | Drums/barrels/cans (for oils) |

---

## API Endpoints

### Base URL

- **Local**: `http://localhost:7071/api`
- **Azure**: `https://<function-app-name>.azurewebsites.net/api`

### GET `/api/health`

Health check endpoint.

**Request**:
```http
GET /api/health
```

**Response** (200 OK):
```json
{
  "status": "ok",
  "message": "NhuTin DB Ingestion Service is running"
}
```

**Use Cases**: Health monitoring, load balancer checks

---

### POST `/api/ingest`

Triggers inventory ingestion from latest Excel file in Google Drive.

**Request**:
```http
POST /api/ingest
Content-Type: application/json
```

**Response** (200 OK):
```json
{
  "status": "ok",
  "filePath": "/tmp/Tong_hop_ton_kho (66).xlsx"
}
```

**Response** (500 Error):
```json
{
  "status": "error",
  "message": "No Excel file found in Google Drive folder"
}
```

or

```json
{
  "status": "error",
  "message": "Unexpected error during ingestion"
}
```

**Error Scenarios**:
- No Excel file found in "Nhu Tin" folder
- Google Drive authentication failure
- Database connection failure
- Excel parsing errors
- Transaction rollback (data integrity issues)

**Idempotency**: Safe to call multiple times (same file can be ingested repeatedly)

---

## Configuration

### Environment Variables

The service uses a fallback chain for configuration (see `config.py`):

1. **`local.settings.json`** → `Values` section (highest priority)
2. **Environment variables** (Azure App Settings)
3. **Default values** (lowest priority)

### Required Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_USER` | PostgreSQL username | `nhutin` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `***` |
| `POSTGRES_HOST` | PostgreSQL hostname | `nhutin-psql.postgres.database.azure.com` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DATABASE` | PostgreSQL database name | `postgres` |
| `GoogleServiceAccount` | Google Service Account JSON (dict or JSON string) | `{...}` |

### Optional Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `FORM_RECOGNIZER_ENDPOINT` | Azure Form Recognizer endpoint | `https://...` |
| `FORM_RECOGNIZER_KEY` | Azure Form Recognizer key | `***` |

### `local.settings.json` Format

```json
{
  "IsEncrypted": false,
  "Values": {
    "POSTGRES_USER": "nhutin",
    "POSTGRES_PASSWORD": "***",
    "POSTGRES_HOST": "nhutin-psql.postgres.database.azure.com",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DATABASE": "postgres",
    "FUNCTIONS_WORKER_RUNTIME": "python"
  },
  "GoogleServiceAccount": {
    "type": "service_account",
    "project_id": "...",
    "private_key_id": "...",
    "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
    "client_email": "...",
    ...
  }
}
```

**Note**: `GoogleServiceAccount` can be:
- Top-level key (dict)
- Under `Values` (dict or JSON string)

---

## Development

### Prerequisites

- Python 3.9+ (Azure Functions Python worker requirement)
- PostgreSQL database (local or Azure)
- Google Service Account with Drive API access
- Azure Functions Core Tools (for local testing)

### Setup

```bash
# Clone repository
git clone <repository-url>
cd nhutin-backend

# Install dependencies
pip install -r requirements.txt

# Configure (copy and edit)
cp local.settings.json.example local.settings.json
# Edit local.settings.json with your credentials

# Initialize database schema (optional, auto-initialized on ingestion)
python -m services.database
```

### Project Structure

```
nhutin-backend/
├── function_app.py          # Azure Functions HTTP triggers
├── main.py                   # Local testing script
├── config.py                 # Configuration management
├── schema.psql              # Database schema
├── host.json                # Azure Functions host configuration
├── local.settings.json       # Local configuration (gitignored)
├── requirements.txt          # Python dependencies
├── services/
│   ├── database.py          # Database connection & schema
│   ├── fetcher.py           # Google Drive file fetcher
│   ├── inventory.py         # Inventory ingestion logic
│   └── normalizer.py        # Item normalization & classification
├── docs/
│   ├── agent.md             # Technical documentation
│   └── RULES.md             # Development rules
├── data/                     # Sample Excel files (gitignored)
└── README.md                 # This file
```

### Running Locally

**Option 1: Direct Python Script**
```bash
python main.py
```

**Option 2: Azure Functions Runtime**
```bash
func start
```

Then call:
```bash
curl http://localhost:7071/api/health
curl -X POST http://localhost:7071/api/ingest
```

### Code Style

- **Naming**: camelCase for variables (per user rules)
- **File Length**: Max 200 lines (split into multiple classes/files if longer)
- **Error Handling**: Structured error handling with specific failure modes
- **Documentation**: Docstrings for all functions
- **Logging**: Use `logger` from `config.py` for all log messages
- **File Operations**: Only write to `/tmp` (Azure Functions requirement)

---

## Testing

### Testing Individual Components

**Database Connection & Schema**:
```bash
python -m services.database
```

**Google Drive Fetcher**:
```bash
python -m services.fetcher
```

**Item Normalizer** (shows classification examples):
```bash
python -m services.normalizer
```

**Inventory Ingestion** (uses `data/Tong_hop_ton_kho (66).xlsx`):
```bash
python -m services.inventory
```

**Full Pipeline**:
```bash
python main.py
```

### Testing Azure Functions Locally

```bash
# Start Functions runtime
func start

# In another terminal, test endpoints
curl http://localhost:7071/api/health
curl -X POST http://localhost:7071/api/ingest
```

### Test Data

Sample Excel files should be placed in `data/` directory:
- `data/Tong_hop_ton_kho (66).xlsx` (used by `services/inventory.py` test)

**Note**: `data/` directory is gitignored (do not commit Excel files)

---

## Deployment

### Azure Functions Deployment

**Prerequisites**:
- Azure Functions App created
- PostgreSQL database (Azure Database for PostgreSQL Flexible Server)
- Google Service Account configured
- App Settings configured (see [Configuration](#configuration))

**Deployment Steps**:

1. **Configure App Settings** in Azure Portal:
   - `POSTGRES_USER`
   - `POSTGRES_PASSWORD`
   - `POSTGRES_HOST`
   - `POSTGRES_PORT`
   - `POSTGRES_DATABASE`
   - `GoogleServiceAccount` (JSON string)

2. **Deploy Function App**:
   ```bash
   func azure functionapp publish <function-app-name>
   ```

3. **Verify Deployment**:
   ```bash
   curl https://<function-app-name>.azurewebsites.net/api/health
   ```

### Database Setup

The database schema is automatically initialized on first ingestion via `Database.initSchema()`. However, you can manually initialize:

```bash
python -m services.database
```

**Note**: Schema initialization is idempotent (`CREATE TABLE IF NOT EXISTS`)

### Google Drive Setup

1. **Create Service Account** in Google Cloud Console
2. **Enable Drive API** for the project
3. **Share "Nhu Tin" folder** with service account email
4. **Add Service Account JSON** to `local.settings.json` or Azure App Settings

### Monitoring

- **Application Insights**: Configured via Azure Functions (if enabled)
- **Logs**: View in Azure Portal → Function App → Logs
- **Errors**: Check Function App logs for detailed error messages

---

## Troubleshooting

### Common Issues

**"No Excel file found in Google Drive folder"**
- Verify "Nhu Tin" folder exists and is shared with service account
- Check service account email has access
- Verify folder name matches exactly (case-sensitive)

**"GoogleServiceAccount not found"**
- Check `local.settings.json` has `GoogleServiceAccount` key
- Verify JSON format is valid
- Check environment variables if deployed

**Database connection errors**
- Verify PostgreSQL credentials in `local.settings.json` or App Settings
- Check firewall rules allow Azure Functions IPs
- Verify database server is running

**Schema initialization failures**
- Check `schema.psql` file exists in project root
- Verify database user has CREATE TABLE permissions
- Check logs for specific SQL errors

**Excel parsing errors**
- Verify Excel file format matches expected structure
- Check row 2 has Vietnamese date format
- Verify data starts at row 6

---

## License

Private — NhuTin internal use only.

---

## Additional Documentation

- [Agent Documentation](docs/agent.md) — Detailed technical documentation
- [Development Rules](docs/RULES.md) — Code quality and documentation standards
- [Changelog](CHANGELOG.md) — Version history and changes
