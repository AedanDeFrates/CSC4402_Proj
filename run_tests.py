"""Run the five test queries in test_queries.sql and print the results.

Usage:
    python run_tests.py --password YOUR_MYSQL_PASSWORD
    python run_tests.py --password ... > test_output.txt     (save output for the report)

Exit code is 0 if every query ran, 1 if any query raised an error.
"""
import argparse
import os
import re
import sys

from mysql.connector import Error

from db_connect import add_connection_args, connect

HERE = os.path.dirname(os.path.abspath(__file__))


def load_tests(path):
    """Return [(title, sql), ...] from a file that uses '-- TEST n: title' markers."""
    tests, title, lines = [], None, []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            marker = re.match(r"--\s*TEST\s*\d+\s*:\s*(.*)", line)
            if marker:
                if title is not None:
                    tests.append((title, "".join(lines).strip().rstrip(";")))
                title, lines = marker.group(1).strip(), []
            elif not line.lstrip().startswith("--"):
                lines.append(line)
    if title is not None:
        tests.append((title, "".join(lines).strip().rstrip(";")))
    return tests


def print_table(columns, rows):
    text_rows = [["NULL" if v is None else str(v) for v in row] for row in rows]
    widths = [max(len(str(c)), *(len(r[i]) for r in text_rows)) if text_rows else len(str(c))
              for i, c in enumerate(columns)]
    print("  " + " | ".join(str(c).ljust(w) for c, w in zip(columns, widths)))
    print("  " + "-+-".join("-" * w for w in widths))
    for r in text_rows:
        print("  " + " | ".join(v.ljust(w) for v, w in zip(r, widths)))
    print(f"  ({len(text_rows)} row{'s' if len(text_rows) != 1 else ''})")


def main():
    parser = argparse.ArgumentParser(description="Run the test queries.")
    add_connection_args(parser)
    parser.add_argument("--queries", type=str, default=os.path.join(HERE, "test_queries.sql"))
    args = parser.parse_args()

    try:
        tests = load_tests(args.queries)
    except FileNotFoundError:
        print(f"Error: could not find {args.queries}")
        sys.exit(1)

    failures = 0
    connection = None
    try:
        connection = connect(args)
        cursor = connection.cursor()
        for number, (title, sql) in enumerate(tests, start=1):
            print(f"\nTEST {number}: {title}")
            try:
                cursor.execute(sql)
                print_table([d[0] for d in cursor.description], cursor.fetchall())
            except Error as e:
                failures += 1
                print(f"  FAILED: {e}")
    except Error as e:
        print(f"DB error: {e}")
        sys.exit(1)
    finally:
        if connection is not None and connection.is_connected():
            connection.close()

    print(f"\n{len(tests) - failures}/{len(tests)} queries ran successfully.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
