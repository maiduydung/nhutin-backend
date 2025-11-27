import os
import psycopg2
from config import POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE, logger


class Database:
    """PostgreSQL database connection and schema management."""

    # Schema file path (relative to project root)
    SCHEMA_FILE = "schema.psql"

    @staticmethod
    def getDbConnection():
        """Create and return a new database connection."""
        connection = psycopg2.connect(
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DATABASE,
        )
        return connection

    @classmethod
    def initSchema(cls):
        """
        Initialize database schema by running schema.psql.
        Uses CREATE TABLE IF NOT EXISTS, safe to run multiple times.
        """
        # Find schema file (check multiple locations)
        schemaPath = cls._findSchemaFile()
        
        if not schemaPath:
            logger.warning("⚠️ Schema file not found, skipping initialization")
            return False

        connection = cls.getDbConnection()
        cursor = connection.cursor()

        try:
            with open(schemaPath, 'r') as f:
                schemaSql = f.read()
            
            cursor.execute(schemaSql)
            connection.commit()
            logger.info("✅ Database schema initialized successfully")
            return True

        except Exception as e:
            connection.rollback()
            logger.error(f"❌ Failed to initialize schema: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    @classmethod
    def _findSchemaFile(cls) -> str | None:
        """
        Find the schema.psql file in common locations.
        Returns the path if found, None otherwise.
        """
        # Possible locations
        locations = [
            cls.SCHEMA_FILE,  # Current directory
            os.path.join(os.path.dirname(__file__), '..', cls.SCHEMA_FILE),  # Project root
            os.path.join('/tmp', cls.SCHEMA_FILE),  # Azure Functions temp
        ]

        for path in locations:
            if os.path.exists(path):
                return path

        return None


def main():
    """Test database connection and schema initialization."""
    logger.info("🔌 Testing database connection...")
    
    try:
        conn = Database.getDbConnection()
        conn.close()
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return

    logger.info("📋 Initializing schema...")
    Database.initSchema()


if __name__ == "__main__":
    main()

