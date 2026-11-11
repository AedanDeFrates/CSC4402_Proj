CREATE TABLE Employees (
	employee_id INT AUTO_INCREMENT PRIMARY KEY,
	employee_role VARCHAR(15) CHECK (employee_role IN ('manager', 'bar_tender')), -- only two rn
	employee_name VARCHAR(30),

	passcode VARCHAR(4) NOT NULL UNIQUE
);

CREATE TABLE Menu_Items (
	menu_id INT AUTO_INCREMENT PRIMARY KEY,
	drink_name VARCHAR(15),
	price FLOAT(8) NOT NULL
	-- ingredients INT[] -- Array of Stock Item primary key(s)
);

CREATE TABLE Stock_Items (
	stock_id INT AUTO_INCREMENT PRIMARY KEY,

	stock_name VARCHAR(20) NOT NULL UNIQUE,
	item_type VARCHAR(10) CHECK (item_type IN ('beer', 'wine', 'liquor')),
	bottle_count INT DEFAULT 0, -- for beer this is a normal count, but for liquor and Wine this is all currently unopened bottles
	bottle_size_oz INT, -- can be null for beer
	open_bottle_oz float(4), -- 0 means no open bottle, should be less than bottle size
	serving_size FLOAT(4) -- for liquor only
);

-- Intermediary Table: (Many-To-Many) Tracks relations between Menu_Items and Ingredients
CREATE TABLE Menu_Item_Ingredients (
	menu_id INT,
	stock_id INT,
	
	PRIMARY KEY (menu_id, stock_id),
	FOREIGN KEY (menu_id) REFERENCES Menu_Items(menu_id),
	FOREIGN KEY (stock_id) REFERENCES Stock_Items(stock_id)
);

-- Alcohols a menu item can be made with (for example, Tito's or Grey Goose).
CREATE TABLE Menu_Item_Alcohol_Options (
	menu_id INT,
	stock_id INT,

	PRIMARY KEY (menu_id, stock_id),
	FOREIGN KEY (menu_id) REFERENCES Menu_Items(menu_id),
	FOREIGN KEY (stock_id) REFERENCES Stock_Items(stock_id)
);

CREATE TABLE Sales (
	sale_id INT AUTO_INCREMENT PRIMARY KEY,
	sale_time DATETIME DEFAULT CURRENT_TIMESTAMP,
	employee_id INT NOT NULL,

	FOREIGN KEY (employee_id) REFERENCES Employees(employee_id)
);

-- Intermediary Table: (Many-To-Many) Tracks relations between menu items and sales
CREATE TABLE Sale_Menu_Items (
	sale_id INT,
	menu_id INT,
	alcohol_stock_id INT NULL,

	PRIMARY KEY (sale_id, menu_id),
	FOREIGN KEY (sale_id) REFERENCES Sales(sale_id),
	FOREIGN KEY (menu_id) REFERENCES Menu_Items(menu_id),
	FOREIGN KEY (menu_id, alcohol_stock_id)
		REFERENCES Menu_Item_Alcohol_Options(menu_id, stock_id)
);