from config import POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE
import psycopg2


class Database:
    def __init__(self):
        self.connection = self.getDbConnection()

    @staticmethod
    def getDbConnection():
        connection = psycopg2.connect(
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DATABASE,
        )
        return connection

    def executeQuery(self, query: str, params: tuple = None):
        with self.connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def commit(self):
        self.connection.commit()

    def close(self):
        if self.connection:
            self.connection.close()