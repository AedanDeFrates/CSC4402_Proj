import mysql.connector
from mysql.connector import Error
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--password", type=str, default='')
parser.add_argument("--target_db", type=str, default='Bar_Database')
parser.add_argument("--socket_path", type=str, default='/var/run/mysqld/mysqld.sock')
parser.add_argument("--script_path", type=str, default='bar_inv.sql')

args = parser.parse_args()

if __name__=="__main__":

    try:
        connection = mysql.connector.connect(
            user='root',
            password=args.password,
            database=args.target_db,
            unix_socket=args.socket_path,
        )
        cursor = connection.cursor()

        cursor.execute(f'DROP DATABASE IF EXISTS {args.target_db};')
        cursor.execute(f'CREATE DATABASE {args.target_db};')
        cursor.execute(f'USE `{args.target_db}`;')

        with open(args.script_path, 'r', encoding='utf-8') as f:
            sql_script=f.read()
        cursor.execute(sql_script)
        while cursor.nextset():
            pass
        connection.commit()
    except Error as e:
        print(f"DB error: {e}")
    except FileNotFoundError:
        print(f"error: File Not Found")