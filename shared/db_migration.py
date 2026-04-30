"""Database schema migration utilities for safe schema updates."""

import sqlite3
import logging


def get_existing_columns(conn, table_name):
    """Get existing column names and types from the table.

    Args:
        conn: Database connection
        table_name: Name of the table

    Returns:
        dict: {column_name: type}
    """
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {}
    for row in cursor.fetchall():
        # row: (cid, name, type, notnull, dflt_value, pk)
        columns[row[1]] = row[2]  # name -> type
    return columns


def migrate_schema(conn, table_name, desired_schema):
    """
    Compare existing schema with desired schema and apply ALTER TABLE statements
    for any missing columns.

    Args:
        conn: Database connection
        table_name: Name of the table
        desired_schema: Dict of {column_name: (type, constraints)}
                       e.g., {'delete_on_expire': ('INTEGER', 'NULL')}
    """
    existing_columns = get_existing_columns(conn, table_name)

    for col_name, (col_type, constraints) in desired_schema.items():
        if col_name not in existing_columns:
            try:
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {constraints}"
                conn.execute(alter_sql)
                conn.commit()
                logging.info(f"Added column {col_name} to table {table_name}")
            except sqlite3.OperationalError as e:
                logging.error(f"Failed to add column {col_name} to table {table_name}: {e}")
                raise


def initialize_table(conn, table_name, desired_schema, constraints):
    """
    Initialize a table: create if it doesn't exist, migrate if it does.

    Args:
        conn: Database connection
        table_name: Name of the table
        desired_schema: Dict of {column_name: (type, constraints)}
        constraints: List of additional constraints (e.g., FOREIGN KEY, PRIMARY KEY)
    """
    # Check if the table exists
    cursor = conn.cursor()
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    table_exists = cursor.fetchone()

    if not table_exists:
        # Generate CREATE TABLE statement from desired schema
        column_defs = []
        for col_name, (col_type, col_constraints) in desired_schema.items():
            column_defs.append(f"{col_name} {col_type} {col_constraints}")

        # Add additional constraints
        column_defs.extend(constraints)

        create_sql = f"CREATE TABLE {table_name} ({', '.join(column_defs)});"
        cursor.execute(create_sql)
        conn.commit()
    else:
        # Table exists, migrate schema if needed
        migrate_schema(conn, table_name, desired_schema)
