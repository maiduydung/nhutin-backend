import pandas as pd
import re
from decimal import Decimal
from datetime import datetime
from services.database import Database
from services.normalizer import ItemNormalizer
from config import logger


class Inventory:
    """Handles inventory data ingestion from Excel files."""

    @staticmethod
    def _extractDateFromVietnameseFormat(dateString: str) -> tuple[datetime | None, str]:
        """
        Extract date from Vietnamese format.
        Supports:
          - 'Ngày DD tháng MM năm YYYY' (daily reports)
          - 'Tháng MM năm YYYY' (monthly reports - uses current day)
        Returns a tuple of (datetime object or None, format description).
        """
        try:
            # Try daily format first: "Ngày DD tháng MM năm YYYY"
            dailyPattern = r'Ngày\s+(\d+)\s+tháng\s+(\d+)\s+năm\s+(\d+)'
            dailyMatch = re.search(dailyPattern, dateString)
            
            if dailyMatch:
                day = int(dailyMatch.group(1))
                month = int(dailyMatch.group(2))
                year = int(dailyMatch.group(3))
                logger.info(f"   📆 Parsed daily format: day={day}, month={month}, year={year}")
                return datetime(year, month, day), "daily"
            
            # Try monthly format: "Tháng MM năm YYYY" (uses current day)
            monthlyPattern = r'Tháng\s+(\d+)\s+năm\s+(\d+)'
            monthlyMatch = re.search(monthlyPattern, dateString)
            
            if monthlyMatch:
                month = int(monthlyMatch.group(1))
                year = int(monthlyMatch.group(2))
                # Use current day of month for monthly reports
                currentDay = datetime.now().day
                logger.info(f"   📆 Parsed monthly format: month={month}, year={year}, using current day={currentDay}")
                return datetime(year, month, currentDay), "monthly"
            
            return None, "none"  # No date pattern found
        except Exception as e:
            logger.error(f"❌ Error parsing date: {e}")
            return None, "error"

    @staticmethod
    def _safeInt(value) -> int:
        """
        Safely convert a value to int, handling NaN and None.
        Returns 0 for NaN, None, or empty values.
        """
        if pd.isna(value) or value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _calculateUnitPrice(value: int, quantity: int) -> Decimal | None:
        """
        Calculate unit price from value and quantity.
        Returns None if quantity is zero or negative.
        """
        if quantity > 0 and value > 0:
            return Decimal(str(value)) / Decimal(str(quantity))
        return None

    @staticmethod
    def _insertPriceHistory(cursor, itemId: int, price: Decimal, source: str, effectiveAt: datetime):
        """
        Insert a price record into price_history table.
        Uses ON CONFLICT to avoid duplicate entries for same item/source/date.
        """
        cursor.execute(
            """
            INSERT INTO price_history (item_id, price, source, effective_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
            """,
            (itemId, price, source, effectiveAt),
        )

    @staticmethod
    def _wipeDatabase(cursor):
        """
        Wipe all existing data from the database tables.
        Deletes in order: price_history → inventory_records → items
        to respect foreign key constraints.
        """
        logger.info("🗑️  Wiping existing database data...")
        
        # Delete in order: child tables first, then parent table
        cursor.execute("DELETE FROM price_history;")
        logger.info("   ✓ Deleted all price_history records")
        
        cursor.execute("DELETE FROM inventory_records;")
        logger.info("   ✓ Deleted all inventory_records")
        
        cursor.execute("DELETE FROM items;")
        logger.info("   ✓ Deleted all items")
        
        logger.info("✅ Database wipe complete")

    @staticmethod
    def ingestInventoryFromExcel(filePath: str):
        """
        Ingest inventory data from Excel file and store in database.
        Extracts record date from row 2, data from row 6+.
        Also calculates and stores unit prices in price_history.
        Automatically initializes schema if tables don't exist.
        
        For MVP: Wipes existing database data before ingesting fresh snapshot.
        All operations are wrapped in a transaction for safety.
        """
        # Ensure schema exists before ingestion
        Database.initSchema()

        connection = Database.getDbConnection()
        cursor = connection.cursor()

        try:
            # Wipe existing data before ingesting fresh snapshot
            # This ensures deleted items from the accounting software are also removed here
            Inventory._wipeDatabase(cursor)
            
            # Read first 5 rows to find the date (could be in different rows)
            logger.info("🔍 Searching for date in Excel header rows...")
            dfHeader = pd.read_excel(filePath, sheet_name=0, header=None, nrows=5)
            recordDate = None
            dateFormat = None
            
            # Search through rows 0-4 for date pattern
            for i in range(len(dfHeader)):
                cellValue = str(dfHeader.iloc[i, 0]) if pd.notna(dfHeader.iloc[i, 0]) else ""
                if not cellValue.strip():
                    logger.debug(f"   Row {i}: (empty)")
                    continue
                    
                logger.info(f"   🔎 Row {i}: \"{cellValue[:60]}{'...' if len(cellValue) > 60 else ''}\"")
                parsedDate, dateFormat = Inventory._extractDateFromVietnameseFormat(cellValue)
                
                if parsedDate is not None:
                    recordDate = parsedDate
                    logger.info(f"   ✅ Found date in row {i} ({dateFormat} format): {recordDate.date()}")
                    break
            
            # Fallback to current date if not found
            if recordDate is None:
                recordDate = datetime.now()
                logger.warning("⚠️ No date pattern found in header rows, using current date as fallback")
            
            logger.info(f"📅 Using record date: {recordDate.date()}")
            
            # Read the actual data starting from row 6
            dfRaw = pd.read_excel(filePath, sheet_name=0, header=None, skiprows=5)

            # Column mapping (0-indexed):
            # 0: Warehouse name (ignored)
            # 1: Code
            # 2: Name
            # 3: (empty column)
            # 4: Unit
            # 5: Initial Qty, 6: Initial Value
            # 7: Imported Qty, 8: Imported Value
            # 9: Exported Qty, 10: Exported Value
            # 11: Final Qty, 12: Final Value
            logger.info(f"📊 Reading data rows (skiprows=5)...")
            df = pd.DataFrame({
                "code": dfRaw[1],
                "name": dfRaw[2],
                "unit": dfRaw[4],
                "initial_quantity": dfRaw[5],
                "initial_value": dfRaw[6],
                "imported_quantity": dfRaw[7],
                "imported_value": dfRaw[8],
                "exported_quantity": dfRaw[9],
                "exported_value": dfRaw[10],
                "final_quantity": dfRaw[11],
                "final_value": dfRaw[12],
            })
            logger.info(f"   📋 Total rows in Excel: {len(df)}")

            priceRecordsInserted = 0
            itemsProcessed = 0
            rowsSkipped = 0
            typeStats = {}

            logger.info("🔄 Processing items...")
            for _, row in df.iterrows():
                rawCode = str(row["code"]).strip() if pd.notna(row["code"]) else None
                rawName = str(row["name"]).strip() if pd.notna(row["name"]) else None
                rawUnit = str(row["unit"]).strip() if pd.notna(row["unit"]) else None

                if not rawCode or not rawName:
                    rowsSkipped += 1
                    continue  # Skip rows with missing critical info
                
                # Skip header rows that might have slipped through
                if rawCode.lower() in ['mã hàng', 'ma hang', 'mã_hàng']:
                    rowsSkipped += 1
                    continue

                # Normalize item data
                normalized = ItemNormalizer.normalize(rawCode, rawName, rawUnit)
                
                # Track type statistics
                typeStats[normalized.itemType] = typeStats.get(normalized.itemType, 0) + 1

                # Upsert item with normalized data and type
                cursor.execute(
                    """
                    INSERT INTO items (code, name, type, unit)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (code) DO UPDATE
                    SET name = EXCLUDED.name,
                        type = EXCLUDED.type,
                        unit = EXCLUDED.unit
                    RETURNING id;
                    """,
                    (normalized.code, normalized.name, normalized.itemType, normalized.unit),
                )
                itemId = cursor.fetchone()[0]

                # Parse numeric values using safe conversion (handles NaN)
                initialQty = Inventory._safeInt(row["initial_quantity"])
                initialVal = Inventory._safeInt(row["initial_value"])
                importedQty = Inventory._safeInt(row["imported_quantity"])
                importedVal = Inventory._safeInt(row["imported_value"])
                exportedQty = Inventory._safeInt(row["exported_quantity"])
                exportedVal = Inventory._safeInt(row["exported_value"])
                finalQty = Inventory._safeInt(row["final_quantity"])
                finalVal = Inventory._safeInt(row["final_value"])

                # Upsert inventory record
                cursor.execute(
                    """
                    INSERT INTO inventory_records (
                        item_id, record_date,
                        initial_quantity, initial_value,
                        imported_quantity, imported_value,
                        exported_quantity, exported_value,
                        final_quantity, final_value
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (item_id, record_date) DO UPDATE
                    SET initial_quantity = EXCLUDED.initial_quantity,
                        initial_value = EXCLUDED.initial_value,
                        imported_quantity = EXCLUDED.imported_quantity,
                        imported_value = EXCLUDED.imported_value,
                        exported_quantity = EXCLUDED.exported_quantity,
                        exported_value = EXCLUDED.exported_value,
                        final_quantity = EXCLUDED.final_quantity,
                        final_value = EXCLUDED.final_value;
                    """,
                    (
                        itemId,
                        recordDate.date(),
                        initialQty,
                        initialVal,
                        importedQty,
                        importedVal,
                        exportedQty,
                        exportedVal,
                        finalQty,
                        finalVal,
                    ),
                )

                # Calculate and insert price history from import data
                importPrice = Inventory._calculateUnitPrice(importedVal, importedQty)
                if importPrice:
                    Inventory._insertPriceHistory(cursor, itemId, importPrice, "import", recordDate)
                    priceRecordsInserted += 1

                # Calculate and insert price history from export data
                exportPrice = Inventory._calculateUnitPrice(exportedVal, exportedQty)
                if exportPrice:
                    Inventory._insertPriceHistory(cursor, itemId, exportPrice, "export", recordDate)
                    priceRecordsInserted += 1
                
                itemsProcessed += 1

            connection.commit()
            
            # Log summary
            logger.info("=" * 60)
            logger.info("📊 INGESTION SUMMARY")
            logger.info("=" * 60)
            logger.info(f"   📅 Record date: {recordDate.date()}")
            logger.info(f"   📋 Total Excel rows: {len(df)}")
            logger.info(f"   ✅ Items processed: {itemsProcessed}")
            logger.info(f"   ⏭️  Rows skipped: {rowsSkipped}")
            logger.info(f"   💰 Price records: {priceRecordsInserted}")
            logger.info("   📦 Items by type:")
            for itemType, count in sorted(typeStats.items(), key=lambda x: -x[1]):
                logger.info(f"      • {itemType}: {count}")
            logger.info("=" * 60)
            logger.info("✅ Inventory ingestion complete!")

        except Exception as e:
            connection.rollback()
            logger.error(f"❌ Error during ingestion: {e}")
            logger.error("🔄 Transaction rolled back - database state unchanged")
            raise
        finally:
            cursor.close()
            connection.close()


def main():
    """Test inventory ingestion with a local Excel file."""
    import os
    testFile = os.path.join("data", "Tong_hop_ton_kho (66).xlsx")
    
    if not os.path.exists(testFile):
        logger.error(f"Test file not found: {testFile}")
        return
    
    logger.info(f"🧪 Testing ingestion with: {testFile}")
    Inventory.ingestInventoryFromExcel(testFile)


if __name__ == "__main__":
    main()
