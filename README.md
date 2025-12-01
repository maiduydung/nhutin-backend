# Nhu Tin Backend - Container Item Management & Optimization System

## Overview

This is an Azure Functions-based backend service for managing inventory items and optimizing container configurations. The system helps determine the optimal combination of items to build containers while maintaining weight constraints (3000-3700kg) and profit margins (less than 20% of receipt value).

## Project Purpose

The system processes user requests containing:
- **Container specifications** (type, length)
- **Item model type** (e.g., R2DX)
- **Slat specifications** (e.g., 97mm, 122mm)

It then:
1. Fetches required items from the database based on these specifications
2. Optimizes item selection to keep total weight within **3000-3700kg** range
3. Ensures profit margin stays **below 20%** of the receipt value
4. Returns an optimized item list for container construction

## Architecture

### Technology Stack
- **Runtime**: Azure Functions (Python)
- **Database**: PostgreSQL (Azure Database for PostgreSQL)
- **Data Processing**: pandas, numpy
- **Validation**: Pydantic
- **File Storage**: Google Drive integration for inventory Excel files
- **OCR**: Azure Form Recognizer (configured but not actively used in current implementation)

### Project Structure

```
nhutin-backend/
├── function_app.py          # Main Azure Functions app with API endpoints
├── config.py                # Configuration management (env vars, Key Vault)
├── requirements.txt         # Python dependencies
├── schema.psql              # Database schema definitions
├── local.settings.json      # Local development settings (contains DB credentials)
├── models/
│   └── user_input.py       # Pydantic model for API request validation
├── services/
│   ├── database.py         # PostgreSQL database connection wrapper
│   ├── inventory.py         # Inventory data ingestion from Excel files
│   └── fetcher.py           # Google Drive file fetcher
├── data/                    # Sample data files (Excel, PDFs, images)
└── docs/
    └── RULES.md             # Development and coding standards
```

## Database Schema

### Tables

#### `items`
Stores master item catalog information.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PRIMARY KEY | Unique item identifier |
| `code` | TEXT UNIQUE NOT NULL | Item code (e.g., "R2DX_4.0_21X112MM_23072025_US", "thephop") |
| `name` | TEXT NOT NULL | Item name/description |
| `type` | TEXT NOT NULL | Item category/type (see Item Types below) |
| `unit` | TEXT | Unit of measurement (e.g., "kg", "L", "pcs", "set") |

**Item Types** (found in database):
- `walking_floor_r2dx` - R2DX walking floor systems
- `walking_floor_ksd` - KSD walking floor systems
- `walking_floor_kmd` - KMD walking floor systems
- `steel_box` - Steel box/container items
- `steel_plate` - Steel plate materials
- `steel_i` - I-beam steel
- `steel_u` - U-channel steel
- `steel_pipe` - Steel pipes
- `steel_square` - Square steel
- `stainless_steel` - Stainless steel materials
- `galvanized_sheet` - Galvanized sheet metal
- `aluminum` - Aluminum materials
- `hydraulic_pump` - Hydraulic pump equipment
- `controller` - Control systems
- `container` - Container-related items
- `burning_fuel` - Fuel materials

#### `inventory_records`
Stores historical inventory data with quantities and values.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PRIMARY KEY | Record identifier |
| `item_id` | INTEGER REFERENCES items(id) | Foreign key to items table |
| `record_date` | DATE DEFAULT CURRENT_DATE | Date of inventory record |
| `initial_quantity` | INTEGER | Starting quantity |
| `initial_value` | BIGINT | Starting value (in VND) |
| `imported_quantity` | INTEGER | Quantity imported |
| `imported_value` | BIGINT | Value of imports (in VND) |
| `exported_quantity` | INTEGER | Quantity exported |
| `exported_value` | BIGINT | Value of exports (in VND) |
| `final_quantity` | INTEGER | Ending quantity |
| `final_value` | BIGINT | Ending value (in VND) |

**Unique Constraint**: `(item_id, record_date)` - One record per item per date

**Foreign Key**: `item_id` → `items.id`

#### `price_history`
Stores historical pricing information for items from various sources.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PRIMARY KEY | Record identifier |
| `item_id` | INTEGER REFERENCES items(id) | Foreign key to items table |
| `price` | NUMERIC NOT NULL | Price value (in VND) |
| `source` | TEXT | Price source (e.g., "import", "market", "receipt") |
| `note` | TEXT | Additional notes about the price |
| `effective_at` | TIMESTAMP NOT NULL DEFAULT now() | When this price became effective |

**Unique Constraint**: `(item_id, source, effective_at)` - One price record per item-source-time combination

**Foreign Key**: `item_id` → `items.id`

**Note**: This table is not defined in `schema.psql` but exists in the production database. Consider adding it to the schema file.

## API Endpoints

### Health Check
```
GET /api/health
```
Returns service status.

**Response:**
```json
{
  "status": "ok",
  "message": "NhuTin DB Receipts Processing Service is running"
}
```

### Process Receipt (Main Endpoint)
```
POST /api/process_receipt
Content-Type: application/json
```

**Request Body:**
```json
{
  "containerType": "container_20ft",      // or "container_40ft", etc.
  "containerLength": 6.06,               // Length in meters
  "itemModelType": "R2DX",               // Item model code
  "slatType": "97mm"                     // Slat specification
}
```

**Current Response** (validation only - optimization not yet implemented):
```json
{
  "status": "ok",
  "userInput": {
    "containerType": "container_20ft",
    "containerLength": 6.06,
    "itemModelType": "R2DX",
    "slatType": "97mm"
  }
}
```

**Expected Future Response** (to be implemented):
```json
{
  "status": "ok",
  "optimizedItems": [
    {
      "itemCode": "R2DX 4.0\" 21X112MM 23072025 US",
      "itemName": "Sàn di động để xếp dỡ hàng hóa...",
      "quantity": 7,
      "unit": "Bộ",
      "unitPrice": 248802602,
      "totalValue": 1741618214,
      "weight": 3500.0
    }
  ],
  "totalWeight": 3500.0,
  "totalValue": 1741618214,
  "profitMargin": 15.5,
  "receiptValue": 2000000000
}
```

## Database Statistics (as of inspection)

- **Total Items**: 32 items
- **Total Inventory Records**: 32 records
- **Date Range**: Single date (2025-11-18) in current records
- **Price History Records**: 2 records
- **R2DX Items**: 3 items found
  - `R2DX_4.0_21X112MM_23072025_US` (7 units, unit price: 248,802,602 VND)
  - `R2DX_4.0_21X112MM_MBV/MCV/L_TKHQ3360_10012025` (1 unit, unit price: 213,090,938 VND)
  - `r2dx4_107243803660` (2 units, unit price: 239,647,264 VND)

**Sample Item Units Found**:
- Weight-based: `kg` (for steel, aluminum, fuel materials)
- Volume-based: `L` (for liquids like diesel oil)
- Count-based: `pcs` (pieces), `set` (sets for walking floor systems)

## Current Implementation Status

### ✅ Implemented
1. **Database Infrastructure**
   - PostgreSQL connection wrapper (`services/database.py`)
   - Database schema defined (`schema.psql`)
   - Connection pooling and query execution

2. **Data Ingestion**
   - Excel file parsing (`services/inventory.py`)
   - Vietnamese date format extraction
   - Inventory data import to database
   - Handles: initial, imported, exported, and final quantities/values

3. **Google Drive Integration**
   - Service account authentication (`services/fetcher.py`)
   - Folder and file discovery
   - Latest Excel file download from "Nhu Tin" folder
   - Azure Functions compatible (writes to `/tmp`)

4. **API Framework**
   - Azure Functions HTTP endpoints
   - Request validation with Pydantic
   - Error handling and logging
   - Health check endpoint

5. **Configuration Management**
   - Multi-source config loading (`config.py`)
   - Supports: `local.settings.json`, environment variables
   - Azure Key Vault integration (prepared but commented out)

### ❌ Not Yet Implemented (Core Features)

1. **Item Selection Logic**
   - Querying items by `itemModelType` (e.g., "R2DX")
   - Filtering by container specifications (`containerType`, `containerLength`, `slatType`)
   - Determining which items are needed for a specific container build

2. **Weight Optimization Algorithm**
   - Calculating item weights (weight data not currently in schema)
   - Optimizing item combinations to achieve 3000-3700kg target
   - Handling multiple item types and quantities

3. **Profit Calculation**
   - Receipt value calculation
   - Profit margin computation
   - Ensuring profit < 20% of receipt value
   - Cost vs. selling price logic

4. **Optimization Engine**
   - Constraint satisfaction (weight range, profit margin)
   - Item quantity optimization
   - Multiple solution generation/ranking

## Key Questions for Implementation

### 1. Item-Container Relationship
- **Q**: How do we determine which items are needed for a given container type/length/model?
  - Is there a bill of materials (BOM) table or mapping?
  - Are there formulas based on container length?
  - How does `slatType` affect item selection?

### 2. Weight Data
- **Q**: Where is item weight stored?
  - Is it in the `items` table (needs schema update)?
  - Is it calculated from item dimensions?
  - Is it in a separate table or external data source?

### 3. Profit Calculation
- **Q**: How is profit calculated?
  - Receipt value = selling price to customer?
  - Cost = sum of `final_value` from inventory_records?
  - Profit = Receipt Value - Cost?
  - Which `record_date` should be used for pricing (latest? specific date?)?

### 4. Optimization Constraints
- **Q**: What are the optimization priorities?
  - Maximize profit while staying under 20%?
  - Minimize weight variance from target (e.g., 3350kg)?
  - Are there other constraints (availability, lead time, etc.)?

### 5. Item Availability
- **Q**: How do we check item availability?
  - Use `final_quantity` from latest `record_date`?
  - What if multiple items are needed but quantities are limited?
  - Should we consider `exported_quantity` to avoid double-booking?

### 6. Container Specifications
- **Q**: What do container types mean?
  - `container_20ft` vs `container_40ft` - different item requirements?
  - How does `containerLength` affect item quantities (linear relationship?)?
  - What is `slatType` and how does it impact the build?

## Data Flow

### Inventory Ingestion Flow
```
Google Drive ("Nhu Tin" folder)
    ↓
DriveFetcher.fetchLatestExcelFromFolder()
    ↓
Excel file downloaded to /tmp/
    ↓
Inventory.ingestInventoryFromExcel()
    ↓
Parse Excel (extract date from row 2, data from row 6+)
    ↓
Insert/Update items table
    ↓
Insert/Update inventory_records table
```

### Receipt Processing Flow (To Be Implemented)
```
POST /api/process_receipt
    ↓
Validate UserInput (containerType, containerLength, itemModelType, slatType)
    ↓
Query database for items matching itemModelType
    ↓
Determine required items based on container specs
    ↓
Optimize item quantities:
    - Weight constraint: 3000-3700kg
    - Profit constraint: < 20% of receipt value
    ↓
Return optimized item list
```

## Configuration

### Environment Variables / local.settings.json

Required configuration keys:

```json
{
  "Values": {
    "POSTGRES_USER": "nhutin",
    "POSTGRES_PASSWORD": "your_password",
    "POSTGRES_HOST": "nhutin-psql.postgres.database.azure.com",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DATABASE": "postgres",
    "FORM_RECOGNIZER_ENDPOINT": "https://...",
    "FORM_RECOGNIZER_KEY": "...",
    "GoogleServiceAccount": { /* Service account JSON */ }
  }
}
```

### Database Connection

The `Database` class in `services/database.py` handles PostgreSQL connections. It uses connection pooling and provides:
- `executeQuery(query, params)` - Execute SELECT queries
- `commit()` - Commit transactions
- `close()` - Close connection

**Note**: Current implementation uses a single persistent connection. Consider connection pooling for production.

### Common Query Patterns

**Get items by type** (e.g., R2DX walking floors):
```sql
SELECT id, code, name, unit, type
FROM items
WHERE type = 'walking_floor_r2dx';
```

**Get latest inventory for items**:
```sql
SELECT DISTINCT ON (i.id)
    i.code, i.name, i.unit, i.type,
    ir.record_date, ir.final_quantity, ir.final_value,
    CASE WHEN ir.final_quantity > 0 
         THEN ir.final_value / ir.final_quantity 
         ELSE 0 END as unit_price
FROM items i
LEFT JOIN inventory_records ir ON i.id = ir.item_id
ORDER BY i.id, ir.record_date DESC NULLS LAST;
```

**Get price history for an item**:
```sql
SELECT ph.price, ph.source, ph.effective_at, ph.note
FROM price_history ph
WHERE ph.item_id = (SELECT id FROM items WHERE code = 'R2DX_4.0_21X112MM_23072025_US')
ORDER BY ph.effective_at DESC;
```

**Calculate unit price from inventory** (when price_history not available):
```sql
SELECT 
    i.code,
    ir.final_quantity,
    ir.final_value,
    CASE WHEN ir.final_quantity > 0 
         THEN ir.final_value / ir.final_quantity 
         ELSE 0 END as unit_price
FROM items i
JOIN inventory_records ir ON i.id = ir.item_id
WHERE ir.record_date = (SELECT MAX(record_date) FROM inventory_records)
  AND ir.final_quantity > 0;
```

## Development Guidelines

See `docs/RULES.md` for detailed coding standards. Key points:

- **File length**: Max 200 lines per file
- **Error handling**: Structured error handling required
- **Documentation**: Docstrings for all functions
- **Testing**: Each file should have a `main()` function for testing
- **Azure Functions**: Write files only to `/tmp`
- **Async**: Prioritize async for I/O operations
- **OOP**: Use classes and methods for readability

## Running Locally

### Prerequisites
- Python 3.8+
- PostgreSQL database (or Azure Database for PostgreSQL)
- Azure Functions Core Tools (for local development)

### Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Configure database**:
   - Update `local.settings.json` with your database credentials
   - Run `schema.psql` to create tables:
   ```bash
   psql -h <host> -U <user> -d <database> -f schema.psql
   ```

3. **Ingest inventory data** (optional):
```python
from services.inventory import Inventory
Inventory.ingestInventoryFromExcel("data/Tong_hop_ton_kho (64).xlsx")
```

4. **Run Azure Functions locally**:
```bash
func start
```

5. **Test endpoints**:
   - Health: `GET http://localhost:7071/api/health`
   - Process receipt: `POST http://localhost:7071/api/process_receipt`

## Sample Data

The `data/` directory contains:
- `Tong_hop_ton_kho (64).xlsx` - Sample inventory Excel file
- `So_chi_tiet_vat_tu_hang_hoa.xlsx` - Detailed item list
- `1C25TNT_00000085 VTNguyenHung 18112025.pdf` - Sample receipt/PDF
- `sample_calculation.jpeg` - Sample calculation image
- `Nhu Tin.png` - Company logo/image

## Next Steps for Implementation

1. **Update schema.psql**
   - Add `type` column to `items` table
   - Add `price_history` table definition
   - Ensure schema matches production database

2. **Add weight data to schema**
   - Add `weight_per_unit` column to `items` table, OR
   - Create `item_specifications` table with weight/dimensions
   - This is critical for the 3000-3700kg weight optimization

3. **Create item-container mapping**
   - BOM table or configuration file
   - Define relationships between container specs (`containerType`, `containerLength`, `slatType`) and required items
   - Map `itemModelType` (e.g., "R2DX") to specific item codes

4. **Implement optimization algorithm**
   - Constraint satisfaction solver (weight range: 3000-3700kg)
   - Profit calculation logic (profit < 20% of receipt value)
   - Use `price_history` or `inventory_records.final_value / final_quantity` for unit prices
   - Item quantity optimization

5. **Add receipt processing**
   - PDF parsing (using Form Recognizer?)
   - Extract receipt value
   - Link to optimized item list

6. **Testing**
   - Unit tests for optimization logic
   - Integration tests with database
   - End-to-end API tests

## Notes for Future LLMs

- **Database**: Always use the `Database` class from `services/database.py` for queries
- **Config**: Use `get_config()` from `config.py` for configuration values
- **Logging**: Use `logger` from `config.py` for all logging
- **File I/O**: In Azure Functions, only write to `/tmp` directory
- **Validation**: Use Pydantic models for request/response validation
- **Error Handling**: Follow patterns in `function_app.py` for API error responses
- **Code Style**: Follow `docs/RULES.md` - max 200 lines per file, OOP, async for I/O

## Known Limitations

1. **No weight data**: Item weights are not currently stored in the database (needed for 3000-3700kg optimization)
2. **No BOM**: No bill of materials mapping container specs to items
3. **No optimization**: Core optimization logic is not implemented
4. **Single connection**: Database uses one persistent connection (not pooled)
5. **No caching**: No caching layer for frequently accessed data
6. **Synchronous I/O**: Some operations are synchronous (should be async)
7. **Schema mismatch**: `price_history` table exists in DB but not in `schema.psql`
8. **Schema mismatch**: `items.type` column exists in DB but not in `schema.psql`

## Support & Contact

For questions about business logic, optimization requirements, or data structure, refer to the project maintainer or business stakeholders.
