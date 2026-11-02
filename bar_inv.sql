CREATE TABLE Menu_Item (
	menu_id INT AUTO_INCREMENT PRIMARY KEY,

	price FLOAT(4) NOT NULL
	-- ingredients INT[] -- Array of Stock Item primary key(s)
);

CREATE TABLE Menu_Item_Ingredients (
	menu_id INT,
	stock_id INT,
	
	PRIMARY KEY (menu_id, stock_id),
	FOREIGN KEY (menu_id) REFERENCES Menu_Item(menu_id),
	FOREIGN KEY (stock_id) REFERENCES Stock_Item(stock_id)
);

CREATE TABLE Stock_Item (
	stock_id INT AUTO_INCREMENT PRIMARY KEY,

	stock_name VARCHAR(8) NOT NULL UNIQUE,
	item_type VARCHAR(10) CHECK (item_type IN ('beer', 'wine', 'liquor')),
	bottle_count INT DEFAULT 0, -- for beer this is a normal count, but for liquor and Wine this is all currently unopened bottles
	bottle_size_oz INT, -- can be null for beer
	open_bottle_oz float(4), -- 0 means no open bottle, should be less than bottle size
	serving_size FLOAT(4) -- for liquor only
);

CREATE TABLE Sale_Menu_Items (
	sale_id INT,
	menu_id INT,

	PRIMARY KEY (sale_id, menu_id),
	FOREIGN KEY (sale_id) Sale(sale_id),
	FOREIGN KEY (menu_id) Menu_Item(menu_id)
);

CREATE TABLE Sale (
	sale_id INT AUTO_INCREMENT PRIMARY KEY,
	-- menu_items INT[] -- Array of Menu Item primary key(s)
);