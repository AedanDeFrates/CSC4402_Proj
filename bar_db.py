"""Database work for interface.py and analytics.py lives here (no GUI code).

Every function takes an open connection first. Reads return plain dicts/lists.
Functions raise mysql.connector.Error on database problems (duplicate names, rows that
are still referenced, ...) and interface.py shows that message in a popup.
"""
from mysql.connector import Error  # noqa: F401  (re-exported for interface.py)

import db_connect


def open_connection(args):
    """Connect and turn autocommit on, so every statement is saved immediately.
    Multi-step writes below use start_transaction()/commit() so they succeed or fail as a unit."""
    conn = db_connect.connect(args)
    conn.autocommit = True
    return conn


# ----------------------------------------------------------------- helpers
def _rows(conn, sql, params=()):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()


def _write(conn, sql, params=()):
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
    finally:
        cur.close()


# ------------------------------------------------------------------- login
def verify_passcode(conn, passcode):
    """Return {'employee_id', 'employee_name', 'employee_role'} or None."""
    rows = _rows(conn, "SELECT employee_id, employee_name, employee_role "
                       "FROM Employees WHERE passcode = %s", (passcode,))
    return rows[0] if rows else None


# -------------------------------------------------------------------- menu
def get_menu(conn):
    """Every menu item with the bottles it can be poured from:
    [{'menu_id', 'name', 'type', 'price', 'options': [(stock_id, stock_name), ...]}, ...]"""
    rows = _rows(conn, """
        SELECT m.menu_id, m.drink_name, m.drink_type, m.price, st.stock_id, st.stock_name
        FROM Menu_Items m
        LEFT JOIN Menu_Item_Ingredients mi ON mi.menu_id = m.menu_id
        LEFT JOIN Stock_Items st ON st.stock_id = mi.stock_id
        ORDER BY m.drink_name, st.stock_name""")
    menu = {}
    for r in rows:
        item = menu.setdefault(r["menu_id"], {
            "menu_id": r["menu_id"], "name": r["drink_name"], "type": r["drink_type"],
            "price": float(r["price"]), "options": []})
        if r["stock_id"] is not None:
            item["options"].append((r["stock_id"], r["stock_name"]))
    return list(menu.values())


def add_menu_item(conn, name, drink_type, price, stock_ids):
    cur = conn.cursor()
    try:
        conn.start_transaction()
        cur.execute("INSERT INTO Menu_Items (drink_name, price, drink_type) VALUES (%s, %s, %s)",
                    (name, price, drink_type))
        menu_id = cur.lastrowid
        for sid in stock_ids:
            cur.execute("INSERT INTO Menu_Item_Ingredients (menu_id, stock_id) VALUES (%s, %s)",
                        (menu_id, sid))
        conn.commit()
        return menu_id
    except Error:
        conn.rollback()
        raise
    finally:
        cur.close()


def update_menu_item(conn, menu_id, name, drink_type, price, stock_ids):
    """Update the item and change its pour options (only the differences are touched,
    so options already used by past sales are never deleted by accident)."""
    cur = conn.cursor()
    try:
        conn.start_transaction()
        cur.execute("UPDATE Menu_Items SET drink_name = %s, drink_type = %s, price = %s "
                    "WHERE menu_id = %s", (name, drink_type, price, menu_id))
        have = {r["stock_id"] for r in _rows(
            conn, "SELECT stock_id FROM Menu_Item_Ingredients WHERE menu_id = %s", (menu_id,))}
        want = set(stock_ids)
        for sid in have - want:
            cur.execute("DELETE FROM Menu_Item_Ingredients WHERE menu_id = %s AND stock_id = %s",
                        (menu_id, sid))
        for sid in want - have:
            cur.execute("INSERT INTO Menu_Item_Ingredients (menu_id, stock_id) VALUES (%s, %s)",
                        (menu_id, sid))
        conn.commit()
    except Error:
        conn.rollback()
        raise
    finally:
        cur.close()


def delete_menu_item(conn, menu_id):
    """Fails (Error) if the item appears on past sales: history must not disappear."""
    _write(conn, "DELETE FROM Menu_Items WHERE menu_id = %s", (menu_id,))


# ------------------------------------------------------------------- stock
def list_stock(conn):
    return _rows(conn, "SELECT * FROM Stock_Items ORDER BY item_type, stock_name")


def add_stock(conn, name, item_type, bottle_count, bottle_size_oz, open_oz, serving_size):
    _write(conn, "INSERT INTO Stock_Items (stock_name, item_type, bottle_count, bottle_size_oz, "
                 "open_bottle_oz, serving_size) VALUES (%s, %s, %s, %s, %s, %s)",
           (name, item_type, bottle_count, bottle_size_oz, open_oz, serving_size))


def update_stock(conn, stock_id, name, item_type, bottle_count, bottle_size_oz, open_oz, serving_size):
    _write(conn, "UPDATE Stock_Items SET stock_name = %s, item_type = %s, bottle_count = %s, "
                 "bottle_size_oz = %s, open_bottle_oz = %s, serving_size = %s WHERE stock_id = %s",
           (name, item_type, bottle_count, bottle_size_oz, open_oz, serving_size, stock_id))


def delete_stock(conn, stock_id):
    """Fails (Error) if the item has sales or inventory-count history."""
    _write(conn, "DELETE FROM Stock_Items WHERE stock_id = %s", (stock_id,))


def receive_delivery(conn, stock_id, bottles):
    _write(conn, "UPDATE Stock_Items SET bottle_count = bottle_count + %s WHERE stock_id = %s",
           (bottles, stock_id))


# --------------------------------------------------------------- employees
def list_employees(conn):
    return _rows(conn, "SELECT employee_id, employee_name, employee_role, passcode "
                       "FROM Employees ORDER BY employee_role, employee_name")


def add_employee(conn, name, role, passcode):
    _write(conn, "INSERT INTO Employees (employee_role, employee_name, passcode) VALUES (%s, %s, %s)",
           (role, name, passcode))


def update_employee(conn, employee_id, name, role, passcode):
    _write(conn, "UPDATE Employees SET employee_role = %s, employee_name = %s, passcode = %s "
                 "WHERE employee_id = %s", (role, name, passcode, employee_id))


def delete_employee(conn, employee_id):
    """Fails (Error) if the employee has recorded sales or counts."""
    _write(conn, "DELETE FROM Employees WHERE employee_id = %s", (employee_id,))


# ------------------------------------------------------------------- sales
def record_sales(conn, tabs):
    """Save a night's tabs. `tabs` is a list of
        {'name', 'employee_id', 'opened' (datetime), 'is_comp' (bool),
         'items': [{'menu_id', 'stock_id' (or None), 'qty'}, ...]}
    Tabs with no items are skipped. Everything is saved together or not at all.
    Returns the number of sales (tabs) written."""
    cur = conn.cursor()
    written = 0
    try:
        conn.start_transaction()
        for tab in tabs:
            if not tab["items"]:
                continue
            cur.execute("INSERT INTO Sales (sale_name, sale_time, employee_id, is_comp) "
                        "VALUES (%s, %s, %s, %s)",
                        (tab["name"], tab["opened"], tab["employee_id"], 1 if tab["is_comp"] else 0))
            sale_id = cur.lastrowid
            for item in tab["items"]:
                cur.execute("INSERT INTO Sale_Menu_Items (sale_id, menu_id, alcohol_stock_id, quantity) "
                            "VALUES (%s, %s, %s, %s)",
                            (sale_id, item["menu_id"], item["stock_id"], item["qty"]))
            written += 1
        conn.commit()
        return written
    except Error:
        conn.rollback()
        raise
    finally:
        cur.close()


def sales_count_for_date(conn, night=None):
    """How many sales are recorded, optionally limited to `night` ('YYYY-MM-DD')."""
    sql = "SELECT COUNT(*) AS n FROM Sales"
    params = ()
    if night is not None:
        sql += " WHERE DATE(sale_time) = %s"
        params = (night,)
    return _rows(conn, sql, params)[0]["n"]


def total_revenue(conn, night=None):
    """Paid-sales revenue, optionally limited to `night` ('YYYY-MM-DD')."""
    sql = """
        SELECT COALESCE(SUM(m.price * sm.quantity), 0) AS revenue
        FROM Sales s
        JOIN Sale_Menu_Items sm ON sm.sale_id = s.sale_id
        JOIN Menu_Items m ON m.menu_id = sm.menu_id
        WHERE s.is_comp = 0"""
    params = ()
    if night is not None:
        sql += " AND DATE(s.sale_time) = %s"
        params = (night,)
    return float(_rows(conn, sql, params)[0]["revenue"])


def revenue_by_employee(conn):
    """Return each employee with paid sales, matching test query 1."""
    return _rows(conn, """
        SELECT e.employee_name, e.employee_role,
               COUNT(DISTINCT s.sale_id) AS num_tabs,
               ROUND(SUM(m.price * sm.quantity), 2) AS revenue
        FROM Employees e
        JOIN Sales s ON s.employee_id = e.employee_id
        JOIN Sale_Menu_Items sm ON sm.sale_id = s.sale_id
        JOIN Menu_Items m ON m.menu_id = sm.menu_id
        WHERE s.is_comp = 0
        GROUP BY e.employee_id, e.employee_name, e.employee_role
        ORDER BY revenue DESC""")


def top_selling_drinks(conn, limit=5):
    """Return the best-selling paid menu items, matching test query 2."""
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    return _rows(conn, """
        SELECT m.drink_name, m.drink_type, SUM(sm.quantity) AS units_sold,
               ROUND(SUM(m.price * sm.quantity), 2) AS revenue
        FROM Menu_Items m
        JOIN Sale_Menu_Items sm ON sm.menu_id = m.menu_id
        JOIN Sales s ON s.sale_id = sm.sale_id
        WHERE s.is_comp = 0
        GROUP BY m.menu_id, m.drink_name, m.drink_type
        ORDER BY units_sold DESC, m.drink_name
        LIMIT %s""", (limit,))


def low_inventory(conn):
    """Return stock below the average unopened-bottle count for its type."""
    return _rows(conn, """
        SELECT st.stock_id, st.stock_name, st.item_type, st.bottle_count,
               st.open_bottle_oz
        FROM Stock_Items st
        WHERE st.bottle_count < (
            SELECT AVG(other.bottle_count)
            FROM Stock_Items other
            WHERE other.item_type = st.item_type
        )
        ORDER BY st.item_type, st.bottle_count, st.stock_name""")


def variance_alerts(conn, night=None):
    """Return flagged pour variances for `night` or the latest counted date."""
    if night is None:
        latest = _rows(conn, """
            SELECT MAX(count_date) AS latest_night
            FROM Inventory_Counts""")[0]["latest_night"]
        if latest is None:
            return []
        night = latest
    alerts = [row for row in variance_report(conn, night) if row["flag"] == "CHECK"]
    return sorted(alerts, key=lambda row: row["variance"], reverse=True)[:10]


# ---------------------------------------------------- counts and variance
def _count_exists(conn, stock_id, night, kind):
    return bool(_rows(conn, "SELECT count_id FROM Inventory_Counts "
                            "WHERE stock_id = %s AND count_date = %s AND count_type = %s",
                      (stock_id, night, kind)))


def save_close_counts(conn, night, employee_id, counts):
    """Record the end-of-night count for `night` ('YYYY-MM-DD').
    `counts` = [{'stock_id', 'bottle_count', 'open_bottle_oz'}, ...].

    For each item:
      * the 'open' row is whatever Stock_Items holds right now (last night's count plus any
        deliveries). It is only written the first time, so saving twice can't corrupt it.
      * the 'close' row is the new count (re-saving the same night overwrites it).
      * Stock_Items is updated to the new count, so it always shows what is on the shelf.
    """
    cur = conn.cursor()
    try:
        conn.start_transaction()
        for c in counts:
            sid = c["stock_id"]
            if not _count_exists(conn, sid, night, "open"):
                before = _rows(conn, "SELECT bottle_count, open_bottle_oz FROM Stock_Items "
                                     "WHERE stock_id = %s", (sid,))[0]
                cur.execute("INSERT INTO Inventory_Counts (stock_id, employee_id, count_date, count_type, "
                            "bottle_count, open_bottle_oz) VALUES (%s, %s, %s, 'open', %s, %s)",
                            (sid, employee_id, night, before["bottle_count"] or 0,
                             before["open_bottle_oz"] or 0))
            if _count_exists(conn, sid, night, "close"):
                cur.execute("UPDATE Inventory_Counts SET employee_id = %s, bottle_count = %s, "
                            "open_bottle_oz = %s WHERE stock_id = %s AND count_date = %s "
                            "AND count_type = 'close'",
                            (employee_id, c["bottle_count"], c["open_bottle_oz"], sid, night))
            else:
                cur.execute("INSERT INTO Inventory_Counts (stock_id, employee_id, count_date, count_type, "
                            "bottle_count, open_bottle_oz) VALUES (%s, %s, %s, 'close', %s, %s)",
                            (sid, employee_id, night, c["bottle_count"], c["open_bottle_oz"]))
            cur.execute("UPDATE Stock_Items SET bottle_count = %s, open_bottle_oz = %s WHERE stock_id = %s",
                        (c["bottle_count"], c["open_bottle_oz"], sid))
        conn.commit()
    except Error:
        conn.rollback()
        raise
    finally:
        cur.close()


def variance_report(conn, night):
    """Expected vs actual pour for every item that has open AND close counts on `night`.

    used     = open total - close total        (what physically left the bottles)
    expected = sum(quantity * serving size)     (what the sales say was poured, comps included)
    variance = used - expected                  (positive = more left the bottle than was rung up)
    Beer has no bottle size, so one beer counts as 1 unit and a serving as 1 unit.
    """
    rows = _rows(conn, """
        SELECT st.stock_id, st.stock_name, st.item_type,
               op.total_open, cl.total_close,
               COALESCE(ex.expected_used, 0) AS expected_used,
               COALESCE(ex.comp_used, 0) AS comp_used
        FROM Stock_Items st
        JOIN (SELECT ic.stock_id,
                     ic.bottle_count * COALESCE(si.bottle_size_oz, 1) + ic.open_bottle_oz AS total_open
              FROM Inventory_Counts ic JOIN Stock_Items si ON si.stock_id = ic.stock_id
              WHERE ic.count_type = 'open' AND ic.count_date = %s) op ON op.stock_id = st.stock_id
        JOIN (SELECT ic.stock_id,
                     ic.bottle_count * COALESCE(si.bottle_size_oz, 1) + ic.open_bottle_oz AS total_close
              FROM Inventory_Counts ic JOIN Stock_Items si ON si.stock_id = ic.stock_id
              WHERE ic.count_type = 'close' AND ic.count_date = %s) cl ON cl.stock_id = st.stock_id
        LEFT JOIN (SELECT sm.alcohol_stock_id AS stock_id,
                          SUM(sm.quantity * COALESCE(si.serving_size, 1)) AS expected_used,
                          SUM(CASE WHEN s.is_comp = 1 THEN sm.quantity * COALESCE(si.serving_size, 1)
                                   ELSE 0 END) AS comp_used
                   FROM Sale_Menu_Items sm
                   JOIN Sales s ON s.sale_id = sm.sale_id
                   JOIN Stock_Items si ON si.stock_id = sm.alcohol_stock_id
                   WHERE DATE(s.sale_time) = %s
                   GROUP BY sm.alcohol_stock_id) ex ON ex.stock_id = st.stock_id
        ORDER BY st.item_type, st.stock_name""", (night, night, night))
    report = []
    for r in rows:
        opened, closed = float(r["total_open"]), float(r["total_close"])
        expected, comps = float(r["expected_used"]), float(r["comp_used"])
        used = opened - closed
        variance = used - expected
        pct = (variance / expected * 100) if expected else None
        flag = "CHECK" if abs(variance) > max(1.5, 0.10 * expected) else "ok"
        report.append({"stock_id": r["stock_id"], "name": r["stock_name"], "type": r["item_type"],
                       "open": opened, "close": closed, "used": used, "expected": expected,
                       "comps": comps, "variance": variance, "pct": pct, "flag": flag})
    return report
