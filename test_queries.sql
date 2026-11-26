-- Five test queries for the Bar_Database.
-- run_tests.py reads this file: each query starts with a "-- TEST n: title" line.
-- Run:  python run_tests.py --password YOUR_MYSQL_PASSWORD

-- TEST 1: Revenue and number of tabs per employee (comps earn $0, so they are excluded)
SELECT e.employee_name,
       e.employee_role,
       COUNT(DISTINCT s.sale_id) AS num_tabs,
       ROUND(SUM(m.price * sm.quantity), 2) AS revenue
FROM Employees e
JOIN Sales s ON s.employee_id = e.employee_id
JOIN Sale_Menu_Items sm ON sm.sale_id = s.sale_id
JOIN Menu_Items m ON m.menu_id = sm.menu_id
WHERE s.is_comp = 0
GROUP BY e.employee_id, e.employee_name, e.employee_role
ORDER BY revenue DESC;

-- TEST 2: Top 5 best-selling menu items (paid sales only, comps excluded)
SELECT m.drink_name,
       m.drink_type,
       SUM(sm.quantity) AS units_sold,
       ROUND(SUM(m.price * sm.quantity), 2) AS revenue
FROM Menu_Items m
JOIN Sale_Menu_Items sm ON sm.menu_id = m.menu_id
JOIN Sales s ON s.sale_id = sm.sale_id
WHERE s.is_comp = 0
GROUP BY m.menu_id, m.drink_name, m.drink_type
ORDER BY units_sold DESC, m.drink_name
LIMIT 5;

-- TEST 3: Expected ounces poured per stock item on the most recent counted night
SELECT st.stock_name,
       st.item_type,
       SUM(sm.quantity * COALESCE(st.serving_size, 1)) AS expected_oz_poured
FROM Sale_Menu_Items sm
JOIN Sales s ON s.sale_id = sm.sale_id
JOIN Stock_Items st ON st.stock_id = sm.alcohol_stock_id
WHERE DATE(s.sale_time) = (SELECT MAX(count_date) FROM Inventory_Counts)
GROUP BY st.stock_id, st.stock_name, st.item_type
ORDER BY expected_oz_poured DESC;

-- TEST 4: Reorder candidates - stock with fewer unopened bottles than the average for its type
SELECT st.stock_name,
       st.item_type,
       st.bottle_count,
       st.open_bottle_oz
FROM Stock_Items st
WHERE st.bottle_count < (SELECT AVG(st2.bottle_count)
                         FROM Stock_Items st2
                         WHERE st2.item_type = st.item_type)
ORDER BY st.item_type, st.bottle_count, st.stock_name;

-- TEST 5: Pour variance report for the most recent night (positive = more left the bottle than was sold)
SELECT st.stock_name,
       op.count_date,
       ROUND(op.total_open - cl.total_close, 2) AS actual_used,
       ROUND(COALESCE(ex.expected_used, 0), 2) AS expected_used,
       ROUND((op.total_open - cl.total_close) - COALESCE(ex.expected_used, 0), 2) AS variance_oz
FROM Stock_Items st
JOIN (SELECT ic.stock_id,
             ic.count_date,
             ic.bottle_count * COALESCE(si.bottle_size_oz, 1) + ic.open_bottle_oz AS total_open
      FROM Inventory_Counts ic
      JOIN Stock_Items si ON si.stock_id = ic.stock_id
      WHERE ic.count_type = 'open') op ON op.stock_id = st.stock_id
JOIN (SELECT ic.stock_id,
             ic.count_date,
             ic.bottle_count * COALESCE(si.bottle_size_oz, 1) + ic.open_bottle_oz AS total_close
      FROM Inventory_Counts ic
      JOIN Stock_Items si ON si.stock_id = ic.stock_id
      WHERE ic.count_type = 'close') cl
  ON cl.stock_id = op.stock_id AND cl.count_date = op.count_date
LEFT JOIN (SELECT sm.alcohol_stock_id AS stock_id,
                  DATE(s.sale_time) AS sale_date,
                  SUM(sm.quantity * COALESCE(si.serving_size, 1)) AS expected_used
           FROM Sale_Menu_Items sm
           JOIN Sales s ON s.sale_id = sm.sale_id
           JOIN Stock_Items si ON si.stock_id = sm.alcohol_stock_id
           GROUP BY sm.alcohol_stock_id, DATE(s.sale_time)) ex
  ON ex.stock_id = op.stock_id AND ex.sale_date = op.count_date
WHERE op.count_date = (SELECT MAX(count_date) FROM Inventory_Counts)
ORDER BY variance_oz DESC
LIMIT 10;
