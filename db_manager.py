# db_manager.py
# This file manages all interactions with the database using a class-based approach.

import sqlite3
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_file="cyber_database.db"):
        """
        Initialize the DatabaseManager with an SQLite database file.
        
        Args:
            db_file: Path to the SQLite database file
        """
        self.db_file = db_file
        self.conn = None
        self._connect()
    
    def _connect(self):
        """Establish connection to the database"""
        try:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            print(f"Error connecting to SQLite database: {e}")

    def reconnect(self, db_file=None):
        """
        Reconnect to the database, optionally with a different database file
        
        Args:
            db_file: Optional new database file to connect to
        """
        if self.conn:
            self.conn.close()
        
        if db_file:
            self.db_file = db_file
        
        self._connect()

    def show_tables(self):
        """Return a list of all tables in the current database"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [table[0] for table in cursor.fetchall()]

    def create_table(self, table_name, params):
        """
        Create a new table if it doesn't exist
        
        Args:
            table_name: Name of the table to create
            params: SQL parameters for table creation
        """
        tables = self.show_tables()
        if table_name not in tables:
            cursor = self.conn.cursor()
            query = f"CREATE TABLE IF NOT EXISTS {table_name} {params}"
            cursor.execute(query)
            self.conn.commit()
            print(f"Table {table_name} created successfully.")

    def delete_table(self, table_name):
        """Drop a table if it exists"""
        tables = self.show_tables()
        if table_name in tables:
            cursor = self.conn.cursor()
            cursor.execute(f"DROP TABLE {table_name}")
            self.conn.commit()
            print(f"Table {table_name} deleted successfully.")
        else:
            print(f"Table {table_name} does not exist.")

    def insert_row(self, table_name, column_names, column_types, column_values):
        """
        Insert a row into a table
        
        Args:
            table_name: Name of the target table
            column_names: Column names formatted as SQL string
            column_types: Column types formatted as SQL string (used for placeholder counts)
            column_values: Values to insert
        """
        tables = self.show_tables()
        if table_name in tables:
            cursor = self.conn.cursor()
            placeholders = ", ".join(["?"] * len(column_values))
            query = f"INSERT INTO {table_name} {column_names} VALUES ({placeholders})"
            cursor.execute(query, column_values)
            self.conn.commit()
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
        tables = self.show_tables()
        if table_name in tables:
            cursor = self.conn.cursor()
            query = f"DELETE FROM {table_name} WHERE {column_name} = ?"
            cursor.execute(query, (column_value,))
            self.conn.commit()
            print(f"Row deleted from table {table_name} successfully.")
        else:
            print(f"Table {table_name} does not exist.")

    def get_all_rows(self, table_name):
        """
        Get all rows from a table
        
        Args:
            table_name: Name of the target table
            
        Returns:
            List of all rows in the table
        """
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        return cursor.fetchall()

    def get_rows_with_value(self, table_name, column_name, column_value):
        """
        Get rows from a table where a column matches a value
        
        Args:
            table_name: Name of the target table
            column_name: Column to filter on
            column_value: Value to match
            
        Returns:
            List of matching rows
        """
        tables = self.show_tables()
        if table_name in tables:
            cursor = self.conn.cursor()
            query = f"SELECT * FROM {table_name} WHERE {column_name} = ?"
            cursor.execute(query, (column_value,))
            return cursor.fetchall()
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
        tables = self.show_tables()
        if table_name in tables:
            cursor = self.conn.cursor()
            set_clause = ", ".join(f"{col} = ?" for col in column_names)
            query = f"UPDATE {table_name} SET {set_clause} WHERE {primary_key_column} = ?"
            values = list(column_values) + [primary_key_value]
            cursor.execute(query, values)
            self.conn.commit()
            print(f"Row in table {table_name} updated successfully.")
        else:
            print(f"Table {table_name} does not exist.")

    def insert_decrypted_media(self, user_id, media_type_id, path, has_hidden_data=0):
        """
        Insert a record into the `decrypted_media` table.
        
        Args:
            user_id: ID of the user
            media_type_id: Type of media (e.g., 1 for image, 2 for video, 3 for audio)
            path: Path to the decrypted media
            has_hidden_data: Indicator if hidden data was found (0 or 1)
        """
        tables = self.show_tables()
        if "decrypted_media" in tables:
            cursor = self.conn.cursor()
            query = """
                INSERT INTO decrypted_media (user_id, media_type_id, path_to_decrypted_media, has_hidden_data)
                VALUES (?, ?, ?, ?)
            """
            cursor.execute(query, (user_id, media_type_id, path, has_hidden_data))
            self.conn.commit()
            print(f"Media record inserted: User ID={user_id}, Media Type={media_type_id}, Path={path}")
        else:
            print("Table `decrypted_media` does not exist.")

    def get_online_clients(self):
        """Get only currently connected clients (is_online = 1)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM clients WHERE is_online = 1")
        return cursor.fetchall()

    def get_all_clients_with_stats(self):
        """Get statistics for all clients including total uploaded files and hidden data count"""
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
        cursor = self.conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()

    def set_client_online_status(self, user_id, is_online):
        """Update active status for connected client"""
        cursor = self.conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = "UPDATE clients SET is_online = ?, last_login = ? WHERE client_id = ?"
        cursor.execute(query, (1 if is_online else 0, now, user_id))
        self.conn.commit()

    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            print("Database connection closed.")