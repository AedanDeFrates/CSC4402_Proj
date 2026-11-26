"""Generate synthetic sales and nightly inventory counts.

Run this AFTER recreate_db.py and `populate_db.py --pop_all`:

    python populate_sales.py --password YOUR_MYSQL_PASSWORD
    python populate_sales.py --nights 30 --seed 7 --password ...

What it does, for each of the last N nights:
  1. Invents 25-60 sales (tabs), each with 1-4 menu items, at random times 5pm-11:59pm,
     plus (most nights) one COMP sale: drinks on the house / spills that earn $0 (Sales.is_comp = 1).
  2. Tops up stock with "deliveries" if a bottle/keg would run out.
  3. Records an 'open' and a 'close' Inventory_Counts row for every stock item.
     The close count is what was sold PLUS a small random pour error; a few items
     are deliberately "leaky" (8-20% over-pour) so the variance report has something to find.
Finally it writes the last closing count back into Stock_Items (the "current" inventory).

Menu items are linked to bottles by populate_db.py (menu_item_ingredients.json). Only a menu item
that has NO links yet gets random ones here (beer->beer, wine->wine, shot/mix_drink->liquor).
Using --seed makes the output repeatable.
"""
import argparse
import random
import sys
from datetime import date, datetime, timedelta

from mysql.connector import Error

from db_connect import add_connection_args, connect

DEFAULT_SERVING = {"beer": 1.0, "wine": 5.0, "liquor": 1.5}   # oz per pour if the row has none
STOCK_TYPE_FOR = {"beer": "beer", "wine": "wine", "shot": "liquor", "mix_drink": "liquor"}
LINKS_PER_ITEM = {"beer": 1, "wine": 1, "shot": 3, "mix_drink": 3}
DELIVERY_BOTTLES = {"beer": 24, "wine": 6, "liquor": 6}


def unit_size(item):
    """Ounces in one full bottle. Beer has no size, so one beer counts as 1 unit."""
    return item["bottle_size_oz"] or 1


def serving(item):
    return item["serving_size"] or 1


def total_units(bottle_count, open_oz, item):
    return (bottle_count or 0) * unit_size(item) + (open_oz or 0)


def split_units(total, item):
    """Turn a total back into (unopened bottles, ounces left in the open bottle)."""
    size = unit_size(item)
    bottles = int(total // size)
    open_oz = round(total - bottles * size, 2)
    if open_oz >= size - 0.005:        # float rounding guard
        bottles, open_oz = bottles + 1, 0.0
    return bottles, max(open_oz, 0.0)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic sales and inventory counts.")
    add_connection_args(parser)
    parser.add_argument("--nights", type=int, default=14)
    parser.add_argument("--seed", type=int, default=4402)
    args = parser.parse_args()
    random.seed(args.seed)

    connection = None
    try:
        connection = connect(args)
        cur = connection.cursor(dictionary=True)
        run(connection, cur, args)
    except Error as e:
        print(f"DB error: {e}")
        sys.exit(1)
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


def run(connection, cur, args):
    cur.execute("SELECT COUNT(*) AS n FROM Sales")
    if cur.fetchone()["n"] > 0:
        print("Sales already exist. Run recreate_db.py and populate_db.py --pop_all first "
              "to start from a clean database.")
        sys.exit(1)

    cur.execute("SELECT * FROM Employees")
    employees = cur.fetchall()
    cur.execute("SELECT * FROM Menu_Items")
    menu = cur.fetchall()
    cur.execute("SELECT * FROM Stock_Items")
    stock = cur.fetchall()
    if not (employees and menu and stock):
        print("Employees, Menu_Items and Stock_Items must have data. "
              "Run: python populate_db.py --pop_all")
        sys.exit(1)

    # Liquor/wine rows with no serving size get a sensible default so the math works.
    for s in stock:
        if s["serving_size"] is None and s["item_type"] != "beer":
            s["serving_size"] = DEFAULT_SERVING[s["item_type"]]
            cur.execute("UPDATE Stock_Items SET serving_size = %s WHERE stock_id = %s",
                        (s["serving_size"], s["stock_id"]))
    stock_by_id = {s["stock_id"]: s for s in stock}

    # ---- link menu items to the stock items they can be poured from ----
    cur.execute("SELECT menu_id, stock_id FROM Menu_Item_Ingredients")
    links = {}
    for row in cur.fetchall():
        links.setdefault(row["menu_id"], []).append(row["stock_id"])
    pools = {}
    for s in stock:
        pools.setdefault(s["item_type"], []).append(s["stock_id"])
    for m in menu:
        if m["menu_id"] in links:
            continue
        pool = pools.get(STOCK_TYPE_FOR[m["drink_type"]], [])
        if not pool:
            continue
        chosen = random.sample(pool, min(LINKS_PER_ITEM[m["drink_type"]], len(pool)))
        for sid in chosen:
            cur.execute("INSERT INTO Menu_Item_Ingredients (menu_id, stock_id) VALUES (%s, %s)",
                        (m["menu_id"], sid))
        links[m["menu_id"]] = chosen
    sellable = [m for m in menu if links.get(m["menu_id"])]
    if not sellable:
        print("No menu item could be linked to a stock item. Check the starter data.")
        sys.exit(1)

    # Some drinks sell far more than others, so "top sellers" is a meaningful query.
    weights = [random.random() ** 2 + 0.05 for _ in sellable]
    # Pick two "leaky" items among the better sellers, so the variance report has something to find.
    popularity = {}
    for m, weight in zip(sellable, weights):
        for sid in links[m["menu_id"]]:
            popularity[sid] = popularity.get(sid, 0) + weight
    ranked = sorted(popularity, key=lambda sid: -popularity[sid])
    leaky = set(random.sample(ranked[:max(3, len(ranked) // 2)], min(2, len(ranked))))

    bartenders = [e for e in employees if e["employee_role"] == "bar_tender"] or employees
    counter = next((e for e in employees if e["employee_role"] == "manager"), employees[0])
    state = {sid: total_units(s["bottle_count"], s["open_bottle_oz"], s)
             for sid, s in stock_by_id.items()}

    today = date.today()
    total_sales = total_lines = 0

    for offset in range(args.nights, 0, -1):
        night = today - timedelta(days=offset)

        # 1. build the night's sales in memory so we know how much will be poured
        sales, expected = [], {}
        for _ in range(random.randint(25, 60)):
            minute = random.randint(17 * 60, 23 * 60 + 59)
            when = datetime.combine(night, datetime.min.time()) + timedelta(minutes=minute)
            picked = {}
            for m in random.choices(sellable, weights=weights, k=random.randint(1, 4)):
                picked[m["menu_id"]] = m              # one row per menu item per sale
            lines = []
            for menu_id in picked:
                qty = random.choices([1, 2, 3], weights=[70, 22, 8])[0]
                sid = random.choice(links[menu_id])
                expected[sid] = expected.get(sid, 0) + qty * serving(stock_by_id[sid])
                lines.append((menu_id, sid, qty))
            sales.append((when, random.choice(bartenders)["employee_id"], lines, False))

        # a COMP tab: poured but not paid for (still counts as expected pour!)
        if random.random() < 0.7:
            comp_lines = []
            for m in random.sample(sellable, min(len(sellable), random.randint(1, 2))):
                sid = random.choice(links[m["menu_id"]])
                expected[sid] = expected.get(sid, 0) + serving(stock_by_id[sid])
                comp_lines.append((m["menu_id"], sid, 1))
            comp_time = datetime.combine(night, datetime.min.time()) + timedelta(hours=23, minutes=30)
            sales.append((comp_time, random.choice(bartenders)["employee_id"], comp_lines, True))
        sales.sort(key=lambda sale: sale[0])

        # 2. deliveries so nothing runs dry, then the opening snapshot
        for sid, s in stock_by_id.items():
            need = expected.get(sid, 0) * 1.3 + unit_size(s)
            while state[sid] < need:
                state[sid] += DELIVERY_BOTTLES[s["item_type"]] * unit_size(s)
        opening = dict(state)

        # 3. what actually left the bottles = sold + pour error
        for sid, s in stock_by_id.items():
            sold = expected.get(sid, 0)
            error = random.uniform(0.08, 0.20) if sid in leaky else random.uniform(-0.01, 0.04)
            if s["item_type"] == "beer":
                used = round(sold * (1 + error))                 # whole bottles
            else:
                used = round(sold * (1 + error) * 4) / 4         # nearest quarter ounce
            state[sid] -= min(used, state[sid])

        # 4. write everything for the night
        for sid, s in stock_by_id.items():
            for kind, snapshot in (("open", opening[sid]), ("close", state[sid])):
                bottles, open_oz = split_units(snapshot, s)
                cur.execute(
                    "INSERT INTO Inventory_Counts "
                    "(stock_id, employee_id, count_date, count_type, bottle_count, open_bottle_oz) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (sid, counter["employee_id"], night, kind, bottles, open_oz))
        number = 0
        for when, employee_id, lines, is_comp in sales:
            if is_comp:
                name = "COMP"
            else:
                number += 1
                name = f"Tab {number}"
            cur.execute("INSERT INTO Sales (sale_name, sale_time, employee_id, is_comp) "
                        "VALUES (%s, %s, %s, %s)", (name, when, employee_id, 1 if is_comp else 0))
            sale_id = cur.lastrowid
            for menu_id, sid, qty in lines:
                cur.execute(
                    "INSERT INTO Sale_Menu_Items (sale_id, menu_id, alcohol_stock_id, quantity) "
                    "VALUES (%s, %s, %s, %s)", (sale_id, menu_id, sid, qty))
                total_lines += 1
        total_sales += len(sales)
        connection.commit()

    # current inventory = last closing count
    for sid, s in stock_by_id.items():
        bottles, open_oz = split_units(state[sid], s)
        cur.execute("UPDATE Stock_Items SET bottle_count = %s, open_bottle_oz = %s WHERE stock_id = %s",
                    (bottles, open_oz, sid))
    connection.commit()
    print(f"Generated {total_sales} sales ({total_lines} line items) over {args.nights} nights "
          f"and {args.nights * len(stock_by_id) * 2} inventory count rows.")


if __name__ == "__main__":
    main()
