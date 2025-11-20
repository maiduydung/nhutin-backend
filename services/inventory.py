import pandas as pd
import re
from datetime import datetime
from services.database import Database
from config import logger


class Inventory:
    @staticmethod
    def _extractDateFromVietnameseFormat(dateString: str) -> datetime:
        """
        Extract date from Vietnamese format: 'Ngày DD tháng MM năm YYYY'
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
    def ingestInventoryFromExcel(filePath: str):
        """
        Ingests inventory data from Excel file and stores in database.
        Extracts record date from row 2 of the Excel file.
        """
        connection = Database.getDbConnection()
        cursor = connection.cursor()

        try:
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

            for _, row in df.iterrows():
                code = str(row["code"]).strip() if pd.notna(row["code"]) else None
                name = str(row["name"]).strip() if pd.notna(row["name"]) else None
                unit = str(row["unit"]).strip() if pd.notna(row["unit"]) else None

                if not code or not name:
                    continue  # Skip rows with missing critical info

                cursor.execute(
                    """
                    INSERT INTO items (code, name, unit)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (code) DO UPDATE
                    SET name = EXCLUDED.name,
                        unit = EXCLUDED.unit
                    RETURNING id;
                    """,
                    (code, name, unit),
                )
                itemId = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO inventory_records (
                        item_id,
                        record_date,
                        initial_quantity,
                        initial_value,
                        imported_quantity,
                        imported_value,
                        exported_quantity,
                        exported_value,
                        final_quantity,
                        final_value
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
                        int(row["imported_quantity"] or 0),
                        int(row["imported_value"] or 0),
                        int(row["exported_quantity"] or 0),
                        int(row["exported_value"] or 0),
                        int(row["final_quantity"] or 0),
                        int(row["final_value"] or 0),
                    ),
                )

            connection.commit()
            logger.info("✅ Inventory ingestion complete!")

        except Exception as e:
            connection.rollback()
            logger.error(f"❌ Error during ingestion: {e}")
        finally:
            cursor.close()
            connection.close()
