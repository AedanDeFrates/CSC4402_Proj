"""Load the starter data from test_populators/*.json into the database.

Usage:
    python populate_db.py --pop_all --password YOUR_MYSQL_PASSWORD
    python populate_db.py --liquor_pop --employee_pop --menu_pop --password ...

--liquor_pop   loads liquor.json, beer.json and wine.json (all rows of Stock_Items)
--employee_pop loads employees.json
--menu_pop     loads menu_items.json and menu_item_ingredients.json
               (load the stock first: the ingredient links look bottles up by name)

Flags no longer take a value (the old `--pop_all True` form is now just `--pop_all`).
Old bug: argparse `type=bool` treats ANY text, including "False", as True.
"""
import argparse
import json
import os
import sys

from mysql.connector import Error

from db_connect import add_connection_args, connect

HERE = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser(description="Populate the bar database with starter data.")
add_connection_args(parser)
parser.add_argument("--device", type=str, default=None, help=argparse.SUPPRESS)  # old flag, ignored
parser.add_argument("--liquor_pop", action="store_true")
parser.add_argument("--employee_pop", action="store_true")
parser.add_argument("--menu_pop", action="store_true")
parser.add_argument("--pop_all", action="store_true")
args = parser.parse_args()


def load_json(relative_path):
    """Return the parsed JSON file, or [] if the file is missing or empty (wine.json is empty)."""
    path = os.path.join(HERE, relative_path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        print(f"  (skipping {relative_path}: missing or empty)")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_queries():
    path = os.path.join(HERE, "test_populators", "insert_queries.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def liquor_populator(cursor, queries):
    """Stock_Items: liquor, beer and wine all use the same insert."""
    for filename in ("liquor.json", "beer.json", "wine.json"):
        for i in load_json("test_populators/" + filename):
            cursor.execute(queries["liquor"], (
                i["stock_name"],
                i["item_type"],
                i["bottle_count"],
                i["bottle_size_oz"],
                i["open_bottle_oz"],
                i["serving_size"],
            ))


def employee_populator(cursor, queries):
    for i in load_json("test_populators/employees.json"):
        cursor.execute(queries["employee"], (
            i["employee_role"],
            i["employee_name"],
            i["passcode"],
        ))


def menu_populator(cursor, queries):
    for i in load_json("test_populators/menu_items.json"):
        cursor.execute(queries["menu_items"], (
            i["drink_name"],
            i["price"],
            i["drink_type"],
        ))
    # Which bottles each menu item can be poured from (Menu_Item_Ingredients)
    for i in load_json("test_populators/menu_item_ingredients.json"):
        for stock_name in i["stock_names"]:
            cursor.execute(queries["menu_ingredients"], (stock_name, i["drink_name"]))
            if cursor.rowcount == 0:
                print(f"  warning: no link made for {i['drink_name']} -> {stock_name} "
                      f"(is the stock loaded?)")


def main():
    if not (args.pop_all or args.liquor_pop or args.employee_pop or args.menu_pop):
        print("Nothing to do. Pass --pop_all (or --liquor_pop / --employee_pop / --menu_pop).")
        return

    queries = load_queries()
    connection = None
    try:
        connection = connect(args)
        cursor = connection.cursor()
        if args.liquor_pop or args.pop_all:
            liquor_populator(cursor, queries)
        if args.employee_pop or args.pop_all:
            employee_populator(cursor, queries)
        if args.menu_pop or args.pop_all:
            menu_populator(cursor, queries)
        connection.commit()
        cursor.close()
        print("Starter data loaded.")
    except Error as e:
        print(f"DB error: {e}")
        sys.exit(1)
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    main()
