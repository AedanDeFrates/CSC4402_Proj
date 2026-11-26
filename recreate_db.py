"""Drop and rebuild the database from bar_inv.sql.

Usage:
    python recreate_db.py --password YOUR_MYSQL_PASSWORD

WARNING: this deletes the target database and everything in it.
"""
import argparse
import os
import re
import sys

from mysql.connector import Error

from db_connect import add_connection_args, connect

HERE = os.path.dirname(os.path.abspath(__file__))


def split_sql(script):
    """Remove '--' comments, then split into individual statements on ';'."""
    script = re.sub(r"--.*", "", script)
    return [stmt.strip() for stmt in script.split(";") if stmt.strip()]


def main():
    parser = argparse.ArgumentParser(description="Drop and recreate the bar database.")
    add_connection_args(parser)
    parser.add_argument("--script_path", type=str, default=os.path.join(HERE, "bar_inv.sql"))
    args = parser.parse_args()

    try:
        with open(args.script_path, "r", encoding="utf-8") as f:
            statements = split_sql(f.read())
    except FileNotFoundError:
        print(f"Error: could not find {args.script_path}")
        sys.exit(1)

    connection = None
    try:
        # Connect WITHOUT selecting a database: it may not exist yet (the old
        # script crashed on a fresh install because it tried to USE it first).
        connection = connect(args, with_database=False)
        cursor = connection.cursor()
        cursor.execute(f"DROP DATABASE IF EXISTS `{args.target_db}`")
        cursor.execute(f"CREATE DATABASE `{args.target_db}`")
        cursor.execute(f"USE `{args.target_db}`")
        for statement in statements:
            cursor.execute(statement)
        connection.commit()
        print(f"Created database '{args.target_db}' with {len(statements)} tables.")
    except Error as e:
        print(f"DB error: {e}")
        sys.exit(1)
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    main()
