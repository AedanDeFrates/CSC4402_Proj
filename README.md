# CSC4402_Proj
Many bars use a spreadsheet system to manually calculate the error in pours for a night. This involves tracking sales and volume  in ounces of open bottles, and then comparing them to previous nights. This involves a lot of manual data transfer for sales data, and is a monotonous task for managers. This makes employee performance analysis far more difficult. We propose an integration of POS data with inventory data. What this means is that the volume of alcohol from all sales will be tracked and compared to the inventory count at the end of the night.

## Python Environment Setup
For our interface, and for populating, setup, and testing the database, we use python with the following env setup.

```bash
conda create -n bar_db python==3.10
conda activate bar_db
pip install mysql-connector-python
pip install PySimpleGUI
```

## MySQL Database Access
In order to access databases in terminal run the following bash command. (You may have to enter a password).

```bash
mysql -u root
```


```MySQL
SHOW DATABASES;
USE Bar_Database;
SHOW TABLES;
```


## Testing and Test Data

```SQL
SHOW Bar_Database

```

## Interface

From PySimpleGUI you can access demos by running the command below in the terminal after running installation instructions.

```bash
PySimpleGUI
```

Our interface script was built by expanding, editing, and reworking Demo_Borderless_Window.py.
