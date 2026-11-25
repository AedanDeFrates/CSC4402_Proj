import json
import mysql.connector
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--device", type=str, default="unix", choices=["unix", "windows", "mac"])
parser.add_argument("--password", type=str, default="")
parser.add_argument("--target_db", type=str, default="Bar_Database")
parser.add_argument("--socket_path", type=str, default="/var/run/mysqld/mysqld.sock")
parser.add_argument("--liquor_pop", type=bool, default=False)
parser.add_argument("--beer_pop", type=bool, default=False)
parser.add_argument("--wine_pop", type=bool, default=False)
parser.add_argument("--employee_pop", type=bool, default=False)
parser.add_argument("--menu_pop", type=bool, default=False)
parser.add_argument("--pop_all", type=bool, default=False)

args = parser.parse_args()

with open("test_populators/insert_queries.json", "r") as f:
    queries = json.load(f)

if args.device == "unix" :
    connection = mysql.connector.connect(
        user="root", 
        password=args.password,
        database=args.target_db,
        unix_socket=args.socket_path)
else : connection = mysql.connector.connect()

cursor = connection.cursor()

def stock_item_populator(item_type: str) -> None:
    file_path = f"test_populators/{item_type}.json"
    with open(file_path, "r", encoding="utf-8") as f:
        contents = f.read()
    if not contents.strip():
        print(f"No {item_type} stock items to populate from {file_path}.")
        return

    stock_items = json.loads(contents)
    for item in stock_items:
        cursor.execute(queries[item_type], (
            item["stock_name"],
            item["item_type"],
            item["bottle_count"],
            item["bottle_size_oz"],
            item["open_bottle_oz"],
            item["serving_size"]
        ))

def liquor_populator() -> None:
    stock_item_populator("liquor")

def beer_populator() -> None:
    stock_item_populator("beer")

def wine_populator() -> None:
    stock_item_populator("wine")

def employee_populator():
    with open("test_populators/employees.json", 'r') as f:
        employees = json.load(f)
    for i in employees:
        cursor.execute(queries["employee"], (
            i["employee_role"],
            i["employee_name"],
            i["passcode"],
        ))
def menu_populator():
    with open("test_populators/menu_items.json", 'r') as f:
        menu_items=json.load(f)
    for i in menu_items:
        cursor.execute(queries["menu_items"], (
            i["drink_name"],
            i["price"],
            i["drink_type"],
        ))

if __name__=="__main__":
    if args.liquor_pop or args.pop_all: liquor_populator()
    if args.beer_pop or args.pop_all: beer_populator()
    if args.wine_pop or args.pop_all: wine_populator()
    if args.employee_pop or args.pop_all: employee_populator()
    if args.menu_pop or args.pop_all : menu_populator()

    connection.commit()
    cursor.close()
    connection.close()