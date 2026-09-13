# db_manager.py
# This file manages all interactions with the database using a class-based approach.
#
# הוחלף מ-SQLite ל-MySQL: כל שאר הקבצים בפרויקט (cyber_server.py, hide_png.py,
# decode_png.py, create_tables.py) ממשיכים לעבוד בלי שינוי, כי ה-API הציבורי
# (get_all_rows, insert_row, update_row וכו') נשאר זהה. רק המימוש הפנימי השתנה.

import threading
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from constants import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE


class DatabaseManager:
    def __init__(self, host=None, user=None, password=None, database=None):
        """
        Initialize the DatabaseManager with a MySQL connection.

        Args:
            host, user, password: Connection credentials; default to constants.py.
            database: Database name (defaults to constants.MYSQL_DATABASE).
                      Accepts a legacy "something.db" value too (the ".db"
                      suffix is stripped) so old call sites keep working.
        """
        if database and database.endswith(".db"):
            database = database[:-3]

        self.host = host or MYSQL_HOST
        self.user = user or MYSQL_USER
        self.password = password or MYSQL_PASSWORD
        self.database = database or MYSQL_DATABASE

        self.conn = None
        # מנעול כדי לשמור על גישה בטוחה למסד הנתונים מכמה threads של לקוחות
        # שונים בו-זמנית (בניגוד ל-SQLite, חיבור MySQL יחיד אינו thread-safe
        # מובנה כשכמה threads משתמשים בו בו-זמנית).
        self._lock = threading.RLock()
        self._connect()

    def _connect(self):
        """Establish connection to MySQL, creating the database if needed."""
        try:
            # מתחברים קודם בלי לבחור database, כדי שנוכל ליצור אותו אם הוא לא קיים
            bootstrap_conn = mysql.connector.connect(
                host=self.host, user=self.user, password=self.password
            )
            bootstrap_cursor = bootstrap_conn.cursor()
            bootstrap_cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self.database}`")
            bootstrap_conn.commit()
            bootstrap_cursor.close()
            bootstrap_conn.close()

            self.conn = mysql.connector.connect(
                host=self.host, user=self.user, password=self.password, database=self.database
            )
        except Error as e:
            print(f"Error connecting to MySQL database: {e}")
            self.conn = None

    def reconnect(self, database=None):
        """
        Reconnect to the database, optionally with a different database name.

        Args:
            database: Optional new database name to connect to
        """
        with self._lock:
            if self.conn:
                try:
                    self.conn.close()
                except Error:
                    pass
            if database:
                self.database = database
            self._connect()

    def _ensure_connection(self):
        """Pings the connection and transparently reconnects if it dropped."""
        try:
            self.conn.ping(reconnect=True, attempts=3, delay=1)
        except Error:
            self._connect()

    def _cursor(self, dictionary=False):
        self._ensure_connection()
        return self.conn.cursor(dictionary=dictionary)

    def show_tables(self):
        """Return a list of all tables in the current database"""
        with self._lock:
            cursor = self._cursor()
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return tables

    def create_table(self, table_name, params):
        """
        Create a new table if it doesn't exist

        Args:
            table_name: Name of the table to create
            params: SQL parameters for table creation (column definitions)
        """
        with self._lock:
            tables = self.show_tables()
            if table_name not in tables:
                cursor = self._cursor()
                query = f"CREATE TABLE IF NOT EXISTS {table_name} {params}"
                cursor.execute(query)
                self.conn.commit()
                cursor.close()
                print(f"Table {table_name} created successfully.")

    def delete_table(self, table_name):
        """Drop a table if it exists"""
        with self._lock:
            tables = self.show_tables()
            if table_name in tables:
                cursor = self._cursor()
                cursor.execute(f"DROP TABLE {table_name}")
                self.conn.commit()
                cursor.close()
                print(f"Table {table_name} deleted successfully.")
            else:
                print(f"Table {table_name} does not exist.")

    def insert_row(self, table_name, column_names, column_types, column_values):
        """
        Insert a row into a table

        Args:
            table_name: Name of the target table
            column_names: Column names formatted as SQL string, e.g. "(a, b, c)"
            column_types: Unused (kept for backward compatibility with call sites)
            column_values: Values to insert
        """
        with self._lock:
            tables = self.show_tables()
            if table_name in tables:
                cursor = self._cursor()
                placeholders = ", ".join(["%s"] * len(column_values))
                query = f"INSERT INTO {table_name} {column_names} VALUES ({placeholders})"
                cursor.execute(query, tuple(column_values))
                self.conn.commit()
                cursor.close()
                print(f"Row inserted into table {table_name} successfully.")
            else:
                print(f"Table {table_name} does not exist.")

    def delete_row(self, table_name, column_name, column_value):
        """
        Delete a row from a table based on a column value

        Args:
            table_name: Name of the target table
            column_name: Column to filter on
            column_value: Value to match for deletion
        """
        with self._lock:
            tables = self.show_tables()
            if table_name in tables:
                cursor = self._cursor()
                query = f"DELETE FROM {table_name} WHERE {column_name} = %s"
                cursor.execute(query, (column_value,))
                self.conn.commit()
                cursor.close()
                print(f"Row deleted from table {table_name} successfully.")
            else:
                print(f"Table {table_name} does not exist.")

    def get_all_rows(self, table_name):
        """
        Get all rows from a table

        Args:
            table_name: Name of the target table

        Returns:
            List of all rows in the table (each row is dict-like, e.g. row["col"])
        """
        with self._lock:
            cursor = self._cursor(dictionary=True)
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            cursor.close()
            return rows

    def get_rows_with_value(self, table_name, column_name, column_value):
        """
        Get rows from a table where a column matches a value

        Args:
            table_name: Name of the target table
            column_name: Column to filter on
            column_value: Value to match

        Returns:
            List of matching rows (dict-like)
        """
        with self._lock:
            tables = self.show_tables()
            if table_name in tables:
                cursor = self._cursor(dictionary=True)
                query = f"SELECT * FROM {table_name} WHERE {column_name} = %s"
                cursor.execute(query, (column_value,))
                rows = cursor.fetchall()
                cursor.close()
                return rows
            else:
                print(f"Table {table_name} does not exist.")
                return []

    def update_row(self, table_name, primary_key_column, primary_key_value, column_names, column_values):
        """
        Update a row in a table

        Args:
            table_name: Name of the target table
            primary_key_column: Primary key column name
            primary_key_value: Primary key value to match
            column_names: List of column names to update
            column_values: List of new values
        """
        with self._lock:
            tables = self.show_tables()
            if table_name in tables:
                cursor = self._cursor()
                set_clause = ", ".join(f"{col} = %s" for col in column_names)
                query = f"UPDATE {table_name} SET {set_clause} WHERE {primary_key_column} = %s"
                values = list(column_values) + [primary_key_value]
                cursor.execute(query, values)
                self.conn.commit()
                cursor.close()
                print(f"Row in table {table_name} updated successfully.")
            else:
                print(f"Table {table_name} does not exist.")

    def add_column_if_missing(self, table_name, column_name, column_def):
        """
        Adds a column to an existing table if it doesn't already exist.
        Safe to call on every startup - a no-op once the column is present.

        Args:
            table_name: Name of the target table
            column_name: Name of the column to ensure exists
            column_def: SQL type/definition for the new column, e.g. "VARCHAR(255)"
        """
        with self._lock:
            cursor = self._cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
                """,
                (self.database, table_name, column_name),
            )
            (count,) = cursor.fetchone()
            if count == 0:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
                self.conn.commit()
                print(f"Column {column_name} added to table {table_name}.")
            cursor.close()

    def insert_decrypted_media(self, user_id, media_type_id, path, has_hidden_data=0):
        """
        Insert a record into the `decrypted_media` table.

        Args:
            user_id: ID of the user
            media_type_id: Type of media (e.g., 1 for image, 2 for video, 3 for audio)
            path: Path to the decrypted media
            has_hidden_data: Indicator if hidden data was found (0 or 1)
        """
        with self._lock:
            tables = self.show_tables()
            if "decrypted_media" in tables:
                cursor = self._cursor()
                query = """
                    INSERT INTO decrypted_media (user_id, media_type_id, path_to_decrypted_media, has_hidden_data)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, (user_id, media_type_id, path, has_hidden_data))
                self.conn.commit()
                cursor.close()
                print(f"Media record inserted: User ID={user_id}, Media Type={media_type_id}, Path={path}")
            else:
                print("Table `decrypted_media` does not exist.")

    def get_online_clients(self):
        """Get only currently connected clients (is_online = 1)"""
        with self._lock:
            cursor = self._cursor(dictionary=True)
            cursor.execute("SELECT * FROM clients WHERE is_online = 1")
            rows = cursor.fetchall()
            cursor.close()
            return rows

    def get_all_clients_with_stats(self):
        """Get statistics for all clients including total uploaded files and hidden data count"""
        with self._lock:
            query = """
                SELECT
                    c.client_id,
                    c.ip_address,
                    c.is_online,
                    c.last_login,
                    COUNT(m.id) AS total_files_uploaded,
                    SUM(CASE WHEN m.has_hidden_data = 1 THEN 1 ELSE 0 END) AS hidden_data_files_count
                FROM clients c
                LEFT JOIN decrypted_media m ON c.client_id = m.user_id
                GROUP BY c.client_id
            """
            cursor = self._cursor(dictionary=True)
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            return rows

    def set_client_online_status(self, user_id, is_online):
        """Update active status for connected client"""
        with self._lock:
            cursor = self._cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            query = "UPDATE clients SET is_online = %s, last_login = %s WHERE client_id = %s"
            cursor.execute(query, (1 if is_online else 0, now, user_id))
            self.conn.commit()
            cursor.close()

    def close(self):
        """Close the database connection"""
        with self._lock:
            if self.conn:
                self.conn.close()
                self.conn = None
                print("Database connection closed.")