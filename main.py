from config import POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE
import psycopg2

def main():

    connection = psycopg2.connect(user=POSTGRES_USER, password=POSTGRES_PASSWORD, host=POSTGRES_HOST, port=POSTGRES_PORT, database=POSTGRES_DATABASE)
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT * FROM inventory_records")
        results = cursor.fetchall()
        print(results)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    main()