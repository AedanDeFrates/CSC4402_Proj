-- Bar inventory / pour-cost database (MySQL 8.0.16+)
-- Tables are created in dependency order: a table must exist before another
-- table can point a FOREIGN KEY at it.

CREATE TABLE Employees (
    employee_id INT AUTO_INCREMENT PRIMARY KEY,
    employee_role VARCHAR(15) CHECK (employee_role IN ('manager', 'bar_tender')), -- only two rn
    employee_name VARCHAR(30),
    passcode VARCHAR(4) NOT NULL UNIQUE
);

CREATE TABLE Menu_Items (
    menu_id INT AUTO_INCREMENT PRIMARY KEY,
    drink_name VARCHAR(40) NOT NULL UNIQUE,   -- was VARCHAR(15): too short for names like 'Long Island Iced Tea'
    drink_type VARCHAR(20) CHECK (drink_type IN ('beer', 'mix_drink', 'shot', 'wine')),
    price FLOAT(8) NOT NULL
);

CREATE TABLE Stock_Items (
    stock_id INT AUTO_INCREMENT PRIMARY KEY,
    stock_name VARCHAR(40) NOT NULL UNIQUE,
    item_type VARCHAR(10) CHECK (item_type IN ('beer', 'wine', 'liquor')),
    bottle_count INT DEFAULT 0,          -- beer: normal count. liquor/wine: all currently UNOPENED bottles
    bottle_size_oz INT,                  -- can be null for beer
    open_bottle_oz FLOAT(4),             -- 0 means no open bottle, should be less than bottle size
    serving_size FLOAT(4)                -- oz per pour (liquor/wine only)
);

-- Many-to-many: which stock items a menu item can be poured from
CREATE TABLE Menu_Item_Ingredients (
    menu_id INT,
    stock_id INT,
    PRIMARY KEY (menu_id, stock_id),
    FOREIGN KEY (menu_id) REFERENCES Menu_Items(menu_id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES Stock_Items(stock_id) ON DELETE CASCADE
);

CREATE TABLE Sales (
    sale_id INT AUTO_INCREMENT PRIMARY KEY,
    sale_name VARCHAR(30),
    sale_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    employee_id INT NOT NULL,
    is_comp TINYINT(1) NOT NULL DEFAULT 0 CHECK (is_comp IN (0, 1)),  -- 1 = spill / drink on the house: poured but earns $0
    FOREIGN KEY (employee_id) REFERENCES Employees(employee_id)
);

-- Many-to-many: which menu items were on which sale.
-- alcohol_stock_id = the specific bottle/keg that was actually poured for this line.
-- FIX: this used to reference Menu_Item_Alcohol_Options, a table that was never created,
--      which made the whole script fail. It now references Menu_Item_Ingredients.
-- NEW: quantity, so "2 x Vodka Soda" is one row.
-- NEW: line_id is the primary key, so one tab can hold the same drink poured from two
--      different bottles (e.g. a Whiskey Ginger made with JACK and another with JAMESON).
CREATE TABLE Sale_Menu_Items (
    line_id INT AUTO_INCREMENT PRIMARY KEY,
    sale_id INT NOT NULL,
    menu_id INT NOT NULL,
    alcohol_stock_id INT NULL,
    quantity INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
    FOREIGN KEY (sale_id) REFERENCES Sales(sale_id) ON DELETE CASCADE,
    FOREIGN KEY (menu_id) REFERENCES Menu_Items(menu_id),
    FOREIGN KEY (menu_id, alcohol_stock_id)
        REFERENCES Menu_Item_Ingredients(menu_id, stock_id)
);

-- NEW: the end-of-night counts the project description is built around.
-- One 'open' and one 'close' snapshot per stock item per business date.
-- Pour variance = (open total - close total) - (ounces the POS says were sold).
CREATE TABLE Inventory_Counts (
    count_id INT AUTO_INCREMENT PRIMARY KEY,
    stock_id INT NOT NULL,
    employee_id INT NOT NULL,            -- who did the count
    count_date DATE NOT NULL,
    count_type VARCHAR(5) NOT NULL CHECK (count_type IN ('open', 'close')),
    bottle_count INT NOT NULL,
    open_bottle_oz FLOAT(4) NOT NULL DEFAULT 0,
    UNIQUE (stock_id, count_date, count_type),
    FOREIGN KEY (stock_id) REFERENCES Stock_Items(stock_id),
    FOREIGN KEY (employee_id) REFERENCES Employees(employee_id)
);
