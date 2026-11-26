# CSC4402_Proj: Bar Inventory and Pour-Cost Tracker

Many bars use a spreadsheet system to manually calculate pour discrepancies for a night. This involves tracking sales and the volume, in ounces, of open bottles, then comparing those amounts to previous nights. Manually transferring sales data is monotonous for managers and makes employee performance analysis more difficult.

We propose integrating point-of-sale (POS) data with inventory data. This allows the volume of alcohol used in sales to be tracked and compared against inventory counts at the end of the night.

## 1. Requirements

- Python 3.10 or newer
- MySQL Server 8.0.16 or newer (older versions silently ignore the `CHECK` constraints)
- Python packages: FreeSimpleGUI and mysql-connector-python

Install the required packages:

```bash
pip install mysql-connector-python FreeSimpleGUI
```

(Optional, if you use Conda: `conda create -n bar_db python==3.10` then `conda activate bar_db` first.)

Make sure the MySQL server is running and you know the password for the `root` user.

Replace `YOUR_PASSWORD` below with your MySQL root password. If your root user has no password, leave out `--password`.

## 2. Build the database

Run these commands in order from the project folder:

**Warning:** Running `recreate_db.py` drops the existing `Bar_Database` database and recreates it. All existing data in that database will be deleted. Back up any data you want to keep before running this script.

```bash
python recreate_db.py --password YOUR_PASSWORD
python populate_db.py --pop_all --password YOUR_PASSWORD
python populate_sales.py --password YOUR_PASSWORD
```

| Script | What it does |
|---|---|
| `recreate_db.py` | Drops the existing `Bar_Database` database, then recreates it using `bar_inv.sql`. All existing data is deleted. |
| `populate_db.py` | Loads employees, stock (liquor, wine, and beer), menu items, and menu-item ingredient associations from `test_populators/*.json`. |
| `populate_sales.py` | Generates synthetic sales and nightly opening/closing inventory counts (`--nights 14` and `--seed 4402` by default). |

The three database setup scripts share these connection options: `--user`, `--password`, `--host`, `--port`, `--target_db`, and `--socket_path`.

`recreate_db.py` also accepts `--script_path` to specify the SQL schema file.

On Linux, the default MySQL socket is used automatically. On Windows and macOS, the scripts connect to `127.0.0.1:3306`.

## 3. Run the test queries

Run:

```bash
python run_tests.py --password YOUR_PASSWORD
```

This runs the five queries in `test_queries.sql` and prints each result.

To save the output to a file:

```bash
python run_tests.py --password YOUR_PASSWORD > test_output.txt
```

| Test | Question it answers |
|---|---|
| 1 | Revenue and number of tabs per employee |
| 2 | Top 5 best-selling menu items |
| 3 | Expected ounces poured per stock item on the most recent counted night |
| 4 | Reorder candidates: stock below the average bottle count for its type |
| 5 | Pour variance: ounces that left the bottles versus ounces the POS says were sold |

You can also inspect the database directly.

First, connect to MySQL from Command Prompt:

```bash
mysql -u root -p
```

Then, after connecting to MySQL, run:

```sql
SHOW DATABASES;
USE Bar_Database;
SHOW TABLES;
SELECT * FROM Stock_Items;
```

## 4. Run the application interface

Run:

```bash
python interface.py --password YOUR_PASSWORD
```

Log in with a 4-digit passcode (starter data: manager `1111`, bartenders `2222`, `3333`, and `4444`).

Bartenders can open tabs and add or remove drinks. Managers also have access to Record Night, Night Close-out, and Admin features.

FreeSimpleGUI is used as the primary GUI package, with PySimpleGUI as a fallback. It was developed by expanding, editing, and reworking `Demo_Borderless_Window.py`.

## 5. Files

| File or folder | Purpose |
|---|---|
| `bar_inv.sql` | Database schema (tables, keys, and constraints) |
| `bar_db.py` | Handles database operations for inventory, menus, employees, and sales. |
| `db_connect.py` | Shared database connection helper |
| `recreate_db.py` | Rebuilds the database from the schema |
| `populate_db.py` | Loads starter data from `test_populators/*.json` |
| `populate_sales.py` | Generates synthetic sales and inventory counts |
| `test_populators/` | JSON files containing starter employee, stock, menu, and ingredient-association data |
| `test_queries.sql` | Contains the five test queries |
| `run_tests.py` | Executes the five test queries |
| `interface.py` | Application user interface |