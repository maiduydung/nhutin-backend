"""
Analytics service for inventory data analysis and visualization.
Provides SQL queries for statistics, trends, and insights.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from services.database import Database
from config import logger


class Analytics:
    """Handles inventory analytics and data aggregation."""

    @staticmethod
    def getSummaryStats() -> dict:
        """
        Get high-level summary statistics of the inventory.
        Returns dict with total items, total value, recent activity, etc.
        """
        connection = Database.getDbConnection()
        cursor = connection.cursor()

        try:
            stats = {}

            # Total unique items
            cursor.execute("SELECT COUNT(*) FROM items;")
            stats["totalItems"] = cursor.fetchone()[0]

            # Item types distribution
            cursor.execute("""
                SELECT type, COUNT(*) as count 
                FROM items 
                GROUP BY type 
                ORDER BY count DESC;
            """)
            stats["itemsByType"] = dict(cursor.fetchall())

            # Latest inventory snapshot (most recent date)
            cursor.execute("""
                SELECT 
                    record_date,
                    SUM(final_quantity) as total_quantity,
                    SUM(final_value) as total_value,
                    COUNT(DISTINCT item_id) as items_count
                FROM inventory_records
                WHERE record_date = (SELECT MAX(record_date) FROM inventory_records)
                GROUP BY record_date;
            """)
            row = cursor.fetchone()
            if row:
                stats["latestSnapshot"] = {
                    "date": row[0].isoformat() if row[0] else None,
                    "totalQuantity": row[1] or 0,
                    "totalValue": row[2] or 0,
                    "itemsCount": row[3] or 0
                }
            else:
                stats["latestSnapshot"] = None

            # Total imports and exports (all time)
            cursor.execute("""
                SELECT 
                    SUM(imported_quantity) as total_imported,
                    SUM(imported_value) as total_imported_value,
                    SUM(exported_quantity) as total_exported,
                    SUM(exported_value) as total_exported_value
                FROM inventory_records;
            """)
            row = cursor.fetchone()
            stats["allTime"] = {
                "totalImported": row[0] or 0,
                "totalImportedValue": row[1] or 0,
                "totalExported": row[2] or 0,
                "totalExportedValue": row[3] or 0
            }

            return stats

        except Exception as e:
            logger.error(f"❌ Error getting summary stats: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def getInventoryTrends(days: int = 30) -> pd.DataFrame:
        """
        Get inventory trends over time.
        Returns DataFrame with date, total_quantity, total_value, imports, exports.
        """
        connection = Database.getDbConnection()

        try:
            query = """
                SELECT 
                    record_date,
                    SUM(final_quantity) as total_quantity,
                    SUM(final_value) as total_value,
                    SUM(imported_quantity) as imports,
                    SUM(imported_value) as import_value,
                    SUM(exported_quantity) as exports,
                    SUM(exported_value) as export_value
                FROM inventory_records
                WHERE record_date >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY record_date
                ORDER BY record_date;
            """
            df = pd.read_sql(query, connection, params=(days,))
            return df

        except Exception as e:
            logger.error(f"❌ Error getting inventory trends: {e}")
            return pd.DataFrame()
        finally:
            connection.close()

    @staticmethod
    def getTopItems(limit: int = 10, metric: str = "value") -> pd.DataFrame:
        """
        Get top items by value or quantity.
        metric: 'value' or 'quantity'
        """
        connection = Database.getDbConnection()

        try:
            orderBy = "final_value" if metric == "value" else "final_quantity"
            query = f"""
                SELECT 
                    i.code,
                    i.name,
                    i.type,
                    ir.final_quantity,
                    ir.final_value,
                    ir.record_date
                FROM items i
                JOIN inventory_records ir ON i.id = ir.item_id
                WHERE ir.record_date = (SELECT MAX(record_date) FROM inventory_records)
                ORDER BY ir.{orderBy} DESC NULLS LAST
                LIMIT %s;
            """
            df = pd.read_sql(query, connection, params=(limit,))
            return df

        except Exception as e:
            logger.error(f"❌ Error getting top items: {e}")
            return pd.DataFrame()
        finally:
            connection.close()

    @staticmethod
    def getItemTypeDistribution() -> pd.DataFrame:
        """
        Get distribution of items by type with value totals.
        """
        connection = Database.getDbConnection()

        try:
            query = """
                SELECT 
                    i.type,
                    COUNT(DISTINCT i.id) as item_count,
                    SUM(ir.final_quantity) as total_quantity,
                    SUM(ir.final_value) as total_value
                FROM items i
                LEFT JOIN inventory_records ir ON i.id = ir.item_id
                    AND ir.record_date = (SELECT MAX(record_date) FROM inventory_records)
                GROUP BY i.type
                ORDER BY total_value DESC NULLS LAST;
            """
            df = pd.read_sql(query, connection)
            return df

        except Exception as e:
            logger.error(f"❌ Error getting type distribution: {e}")
            return pd.DataFrame()
        finally:
            connection.close()

    @staticmethod
    def getPriceHistory(itemCode: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
        """
        Get price history for all items or a specific item.
        """
        connection = Database.getDbConnection()

        try:
            if itemCode:
                query = """
                    SELECT 
                        i.code,
                        i.name,
                        ph.price,
                        ph.source,
                        ph.effective_at
                    FROM price_history ph
                    JOIN items i ON ph.item_id = i.id
                    WHERE i.code = %s
                    ORDER BY ph.effective_at DESC
                    LIMIT %s;
                """
                df = pd.read_sql(query, connection, params=(itemCode, limit))
            else:
                query = """
                    SELECT 
                        i.code,
                        i.name,
                        ph.price,
                        ph.source,
                        ph.effective_at
                    FROM price_history ph
                    JOIN items i ON ph.item_id = i.id
                    ORDER BY ph.effective_at DESC
                    LIMIT %s;
                """
                df = pd.read_sql(query, connection, params=(limit,))

            return df

        except Exception as e:
            logger.error(f"❌ Error getting price history: {e}")
            return pd.DataFrame()
        finally:
            connection.close()

    @staticmethod
    def getMovementAnalysis() -> pd.DataFrame:
        """
        Analyze item movements (imports vs exports) for the latest period.
        """
        connection = Database.getDbConnection()

        try:
            query = """
                SELECT 
                    i.code,
                    i.name,
                    i.type,
                    ir.imported_quantity,
                    ir.imported_value,
                    ir.exported_quantity,
                    ir.exported_value,
                    (ir.imported_quantity - ir.exported_quantity) as net_quantity,
                    (ir.imported_value - ir.exported_value) as net_value,
                    ir.record_date
                FROM items i
                JOIN inventory_records ir ON i.id = ir.item_id
                WHERE ir.record_date = (SELECT MAX(record_date) FROM inventory_records)
                    AND (ir.imported_quantity > 0 OR ir.exported_quantity > 0)
                ORDER BY ABS(ir.imported_value - ir.exported_value) DESC
                LIMIT 50;
            """
            df = pd.read_sql(query, connection)
            return df

        except Exception as e:
            logger.error(f"❌ Error getting movement analysis: {e}")
            return pd.DataFrame()
        finally:
            connection.close()

    @staticmethod
    def searchItems(query: str, limit: int = 20) -> pd.DataFrame:
        """
        Search items by code or name.
        """
        connection = Database.getDbConnection()

        try:
            sqlQuery = """
                SELECT 
                    i.code,
                    i.name,
                    i.type,
                    i.unit,
                    ir.final_quantity,
                    ir.final_value,
                    ir.record_date
                FROM items i
                LEFT JOIN inventory_records ir ON i.id = ir.item_id
                    AND ir.record_date = (SELECT MAX(record_date) FROM inventory_records)
                WHERE i.code ILIKE %s OR i.name ILIKE %s
                ORDER BY i.name
                LIMIT %s;
            """
            searchPattern = f"%{query}%"
            df = pd.read_sql(sqlQuery, connection, params=(searchPattern, searchPattern, limit))
            return df

        except Exception as e:
            logger.error(f"❌ Error searching items: {e}")
            return pd.DataFrame()
        finally:
            connection.close()

    @staticmethod
    def getAllItemsWithLatestInventory() -> pd.DataFrame:
        """
        Get all items with their latest inventory data.
        """
        connection = Database.getDbConnection()

        try:
            query = """
                SELECT 
                    i.id,
                    i.code,
                    i.name,
                    i.type,
                    i.unit,
                    ir.initial_quantity,
                    ir.initial_value,
                    ir.imported_quantity,
                    ir.imported_value,
                    ir.exported_quantity,
                    ir.exported_value,
                    ir.final_quantity,
                    ir.final_value,
                    ir.record_date
                FROM items i
                LEFT JOIN inventory_records ir ON i.id = ir.item_id
                    AND ir.record_date = (SELECT MAX(record_date) FROM inventory_records)
                ORDER BY i.type, i.name;
            """
            df = pd.read_sql(query, connection)
            return df

        except Exception as e:
            logger.error(f"❌ Error getting all items: {e}")
            return pd.DataFrame()
        finally:
            connection.close()

    @staticmethod
    def executeCustomQuery(query: str) -> pd.DataFrame:
        """
        Execute a custom read-only SQL query.
        Only SELECT statements are allowed for safety.
        """
        # Basic safety check
        cleanQuery = query.strip().upper()
        if not cleanQuery.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

        forbiddenKeywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]
        for keyword in forbiddenKeywords:
            if keyword in cleanQuery:
                raise ValueError(f"Query contains forbidden keyword: {keyword}")

        connection = Database.getDbConnection()

        try:
            df = pd.read_sql(query, connection)
            return df

        except Exception as e:
            logger.error(f"❌ Error executing custom query: {e}")
            raise
        finally:
            connection.close()


def main():
    """Test analytics functions."""
    logger.info("🔍 Testing Analytics Service...")

    try:
        stats = Analytics.getSummaryStats()
        logger.info(f"📊 Summary Stats: {stats}")

        topItems = Analytics.getTopItems(5)
        logger.info(f"🏆 Top 5 Items:\n{topItems}")

        typeDistribution = Analytics.getItemTypeDistribution()
        logger.info(f"📈 Type Distribution:\n{typeDistribution}")

    except Exception as e:
        logger.error(f"❌ Analytics test failed: {e}")


if __name__ == "__main__":
    main()

