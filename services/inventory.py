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
    def _extractDateFromVietnameseFormat(dateString: str) -> datetime:
        """
        Extract date from Vietnamese format: 'Ngày DD tháng MM năm YYYY'.
        Returns a datetime object.
        """
        try:
            pattern = r'Ngày\s+(\d+)\s+tháng\s+(\d+)\s+năm\s+(\d+)'
            match = re.search(pattern, dateString)
            
            if match:
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))
                return datetime(year, month, day)
            else:
                logger.warning(f"Could not parse date from: {dateString}, using current date")
                return datetime.now()
        except Exception as e:
            logger.error(f"Error parsing date: {e}, using current date")
            return datetime.now()

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
            
            # Read row 2 (index 1) to extract the date
            dfDate = pd.read_excel(filePath, sheet_name=0, header=None, nrows=2)
            dateString = str(dfDate.iloc[1, 0]) if len(dfDate) > 1 else ""
            recordDate = Inventory._extractDateFromVietnameseFormat(dateString)
            logger.info(f"📅 Extracted record date: {recordDate.date()}")
            
            # Read the actual data starting from row 6
            dfRaw = pd.read_excel(filePath, sheet_name=0, header=None, skiprows=5)

            df = pd.DataFrame({
                "code": dfRaw[1],
                "name": dfRaw[2],
                "unit": dfRaw[3],
                "initial_quantity": dfRaw[4],
                "initial_value": dfRaw[5],
                "imported_quantity": dfRaw[6],
                "imported_value": dfRaw[7],
                "exported_quantity": dfRaw[8],
                "exported_value": dfRaw[9],
                "final_quantity": dfRaw[10],
                "final_value": dfRaw[11],
            })

            priceRecordsInserted = 0

            for _, row in df.iterrows():
                rawCode = str(row["code"]).strip() if pd.notna(row["code"]) else None
                rawName = str(row["name"]).strip() if pd.notna(row["name"]) else None
                rawUnit = str(row["unit"]).strip() if pd.notna(row["unit"]) else None

                if not rawCode or not rawName:
                    continue  # Skip rows with missing critical info

                # Normalize item data
                normalized = ItemNormalizer.normalize(rawCode, rawName, rawUnit)

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

                # Parse numeric values
                importedQty = int(row["imported_quantity"] or 0)
                importedVal = int(row["imported_value"] or 0)
                exportedQty = int(row["exported_quantity"] or 0)
                exportedVal = int(row["exported_value"] or 0)

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
                        int(row["initial_quantity"] or 0),
                        int(row["initial_value"] or 0),
                        importedQty,
                        importedVal,
                        exportedQty,
                        exportedVal,
                        int(row["final_quantity"] or 0),
                        int(row["final_value"] or 0),
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

            connection.commit()
            logger.info(f"✅ Inventory ingestion complete! Price records: {priceRecordsInserted}")

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
