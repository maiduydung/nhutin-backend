# Nhu Tin Backend - Container Item Management & Optimization System

## Overview

This is an Azure Functions-based backend service for managing inventory items and optimizing container configurations. The system helps determine the optimal combination of items to build containers while maintaining weight constraints (3000-6000kg) and profit margins (less than 20% of receipt value).

## Project Purpose

The system processes user requests containing:
- **Container specifications** (type, length)
- **Item model type** (e.g., R2DX)
- **Slat specifications** (e.g., 97mm, 122mm)

It then:
1. Fetches required items from the database based on these specifications
2. Optimizes item selection to keep total weight within **3000-4144kg** range (includes 12% material loss factor)
3. Ensures profit margin stays **at or below 20%** of the receipt value
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
│   ├── fetcher.py           # Google Drive file fetcher
│   ├── weight_calculator.py # Weight calculation utilities for different item types
│   └── optimizer.py         # Container weight and profit optimization engine
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

#### `aluminum_bar_constants`
Stores constants for calculating aluminum bar weights based on slat specifications.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PRIMARY KEY | Record identifier |
| `type` | TEXT | Bar type ("popular" or "uncommon") |
| `size_mm` | INTEGER | Slat size in millimeters (e.g., 97, 112) |
| `thickness_mm` | INTEGER | Bar thickness in millimeters (e.g., 6, 8) |
| `density_kg_per_m` | NUMERIC | Weight density in kg per meter |
| `bars_per_container` | INTEGER | Number of bars per container (21 or 24) |

**Usage**: Used to calculate aluminum bar weight: `containerLength × density_kg_per_m × bars_per_container`

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
  "containerLength": 6.096,              // Length in meters (e.g., 6.096 for 20ft container)
  "itemModelType": "R2DX",               // Walking floor model: "R2DX", "KSD", or "KMD"
  "slatType": "97mm",                    // Slat specification: "97mm" or "112mm"
  "receiptPrice": 600000000              // Receipt price in VND
}
```

**Response:**
```json
{
  "status": "ok",
  "items": [
    {
      "id": 96,
      "code": "R2DX_4.0_21X112MM_23072025_US",
      "name": "Sàn di động để xếp dỡ hàng hóa...",
      "unit": "set",
      "quantity": 1,
      "unitPrice": 248802602.0,
      "totalValue": 248802602.0,
      "weight": 751.0
    },
    {
      "id": 95,
      "code": "Nhôm_thanh_none",
      "name": "Nhôm thanh None",
      "unit": "kg",
      "quantity": 338.4,
      "unitPrice": 123433.0,
      "totalValue": 41770170.0,
      "weight": 338.4
    }
    // ... more items
  ],
  "totalWeight": 3287.39,
  "totalCost": 476137382.0,
  "receiptPrice": 600000000.0,
  "profit": 123862618.0,
  "profitMargin": 20.64,
  "containerBuiltFromMaterials": false
}
```

**Response Fields:**
- `items`: Array of optimized items with quantities, prices, and weights
- `totalWeight`: Total weight in kg (target: 3000-6000kg)
- `totalCost`: Total cost of all items in VND
- `receiptPrice`: Input receipt price in VND
- `profit`: Calculated profit (receiptPrice - totalCost)
- `profitMargin`: Profit margin percentage (must be ≤ 20%)
- `containerBuiltFromMaterials`: Boolean indicating if container was built from raw materials (true when requested container not in inventory)

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
   - Walking floor weight constants (`WALKING_FLOORS` dictionary)
   - Container build specifications (`CONTAINER_BUILD_SPECS`) based on technical document
   - Material type mappings (`CONTAINER_MATERIAL_TYPES`) for database lookups

6. **Weight Calculation System** (`services/weight_calculator.py`)
   - Walking floor weight lookup from config (R2DX: 751kg, KSD: 503kg, KMD: 502kg)
   - Aluminum bar weight calculation from `aluminum_bar_constants` table
   - Galvanized sheet weight calculation (formula: thickness × width × 7850 / 1,000,000)
   - Support for different unit types (kg, set, m)

7. **Optimization Engine** (`services/optimizer.py`)
   - **Fixed Items Selection**:
     - Always includes 1 walking floor set (based on `itemModelType`)
     - Always includes aluminum bars (calculated from `containerLength` and `slatType`)
   - **Variable Items Optimization**:
     - Selects from 10 item types: `steel_box`, `steel_i`, `steel_square`, `steel_u`, `steel_pipe`, `steel_plate`, `galvanized_sheet`, `stainless_steel`, `hydraulic_pump`, `container`
     - Two-pass selection: (1) weight-contributing items by ratio, (2) zero-weight items to fill budget
     - Maximizes variety (uses multiple item types)
     - Greedy algorithm prioritizing weight-to-cost ratio
   - **Zero-Weight Items**:
     - Containers are treated as packaging (weight = 0)
     - Used to fill budget and reduce profit margin
   - **Container Building** (when unavailable):
     - Automatically builds container from raw materials
     - Uses steel frame, galvanized sheets, and aluminum
     - Specs based on THUYETMINHKYTHUAT.pdf (Walking Floor S-Drive KSD 4.25")
     - 20ft: 492kg steel frame, 50m sheets, 378kg aluminum
     - 40ft: 983kg steel frame, 100m sheets, 757kg aluminum
     - Flexible material substitution: aluminum compensates for steel shortfall
   - **Constraints**:
     - Weight: 3000-6000kg (soft limit, prefers under 6000kg)
     - Profit margin: ≤ 25% of receipt price
     - Inventory availability: Respects `final_quantity` from database

8. **Container Builder** (`services/container_builder.py`)
   - Builds containers from raw materials when pre-built containers unavailable
   - Supports 20ft and 40ft container specifications (based on THUYETMINHKYTHUAT.pdf)
   - Checks material availability (steel frame, galvanized sheets, aluminum)
   - **Flexible Material Substitution**: Aluminum can compensate for steel shortfall
   - Respects budget and weight constraints during building
   - Allows scaled building (minimum 50%) when constraints are tight
   - Prevents duplicate items (container build materials excluded from variable optimization)

9. **Receipt Processing API**
   - Full optimization pipeline integrated
   - Returns optimized item list with weights and costs
   - Calculates profit margin and validates constraints

## Optimization Algorithm Details

### Weight Calculation Methods

1. **Walking Floor Sets** (`unit = "set"`):
   - Weight retrieved from `config.WALKING_FLOORS` dictionary
   - R2DX: 751 kg per set
   - KSD: 503 kg per set
   - KMD: 502 kg per set

2. **Aluminum Bars**:
   - Formula: `containerLength × density_kg_per_m × bars_per_container`
   - Density and bars count from `aluminum_bar_constants` table
   - Selected based on `slatType` (97mm or 112mm)
   - System checks inventory availability and falls back to lower density if needed

3. **Steel Items** (`unit = "kg"`):
   - Weight equals quantity (quantity is already in kilograms)
   - Applies to: `steel_box`, `steel_i`, `steel_square`, `steel_u`, `steel_pipe`

4. **Galvanized Sheets** (`unit = "m"`):
   - Formula: `Thickness (mm) × Width (mm) × 7850 / 1,000,000 = kg/m`
   - Dimensions extracted from item name (e.g., "0.95 x 1200" → 0.95mm × 1200mm)
   - Density of galvanized steel: 7850 kg/m³

### Optimization Strategy

The optimizer uses a **greedy algorithm** with a two-pass approach:

1. **Fixed Items** (always included):
   - Select 1 walking floor set matching `itemModelType`
   - Calculate and include aluminum bars based on `containerLength` and `slatType`

2. **Variable Items Selection** (Two-Pass):
   - **Pass 1 - Weight-Contributing Items**:
     - Groups items by type (steel, galvanized sheets, etc.)
     - Selects at least one item from each available type (for variety)
     - Prioritizes items with best weight-to-cost ratio (kg per VND)
     - Fills remaining weight capacity with best-ratio items
   - **Pass 2 - Zero-Weight Items**:
     - Adds items like containers (weight = 0) to fill remaining budget
     - These items don't affect weight but reduce profit margin

3. **Supported Variable Item Types**:
   - `steel_box`, `steel_i`, `steel_square`, `steel_u`, `steel_pipe`, `steel_plate`
   - `galvanized_sheet`, `stainless_steel`, `hydraulic_pump`, `container`

4. **Constraints Enforcement**:
   - **Weight**: Targets 3000-6720kg range (base 6000kg + 12% material loss factor)
   - **Profit Margin**: Ensures `(receiptPrice - totalCost) / receiptPrice ≤ 0.20` (20%)
   - **Inventory**: Respects `final_quantity` from latest inventory records
   - **Budget Filling**: If profit margin exceeds 20%, adds more materials to fill budget

### Profit Calculation

- **Cost**: Sum of `(quantity × unitPrice)` for all selected items
- **Unit Price**: Calculated as `final_value / final_quantity` from latest inventory record
- **Profit**: `receiptPrice - totalCost`
- **Profit Margin**: `(profit / receiptPrice) × 100%`
- **Constraint**: Profit margin must be ≤ 20%

**Material Loss Factor**: The optimizer accounts for 12% material loss during processing:
- Base weight limit: 6000 kg (target cargo weight)
- With material loss: up to 6720 kg of raw materials can be used
- After processing (cutting, shaping), expect ~6000 kg of usable cargo

**Note**: If the database doesn't have enough inventory to meet the profit margin target, the optimizer will use all available inventory and return the best possible result.

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
    - Weight constraint: 3000-6000kg
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
   - This is critical for the 3000-6000kg weight optimization

3. **Create item-container mapping**
   - BOM table or configuration file
   - Define relationships between container specs (`containerType`, `containerLength`, `slatType`) and required items
   - Map `itemModelType` (e.g., "R2DX") to specific item codes

4. **Implement optimization algorithm**
   - Constraint satisfaction solver (weight range: 3000-6000kg)
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

1. **No weight data**: Item weights are not currently stored in the database (needed for 3000-6000kg optimization)
2. **No BOM**: No bill of materials mapping container specs to items
3. **No optimization**: Core optimization logic is not implemented
4. **Single connection**: Database uses one persistent connection (not pooled)
5. **No caching**: No caching layer for frequently accessed data
6. **Synchronous I/O**: Some operations are synchronous (should be async)
7. **Schema mismatch**: `price_history` table exists in DB but not in `schema.psql`
8. **Schema mismatch**: `items.type` column exists in DB but not in `schema.psql`

## Support & Contact

For questions about business logic, optimization requirements, or data structure, refer to the project maintainer or business stakeholders.
