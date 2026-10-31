CREATE TABLE Menu_Item (
	menue_id int AUTO_INCREMENT PRIMARY KEY,
	price FLOAT(4) NOT NULL,
	
)

CREATE TABLE Stock_Item (
	stock_id int AUTO_INCREMENT PRIMARY KEY,
	name varchar(8) NOT NULL UNIQUE,

)

CREATE TABLE Sale (
	sale_id int AUTO_INCREMENT PRIMARY KEY,
	name varchar(8) NOT NULL UNIQUE,

)


