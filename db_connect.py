"""Shared database connection helper.

Every script (recreate_db.py, populate_db.py, populate_sales.py, run_tests.py)
uses this so the connection options are identical everywhere.

* Linux with the default MySQL socket present -> connects through the socket
  (this is how the original scripts worked).
* Windows / macOS / anything else -> connects over TCP to localhost:3306.
"""
import os

import mysql.connector

DEFAULT_SOCKET = "/var/run/mysqld/mysqld.sock"


def add_connection_args(parser):
    """Add the standard connection options to an argparse parser."""
    parser.add_argument("--user", type=str, default="root")
    parser.add_argument("--password", type=str, default="")
    parser.add_argument("--target_db", type=str, default="Bar_Database")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument(
        "--socket_path",
        type=str,
        default=DEFAULT_SOCKET if os.path.exists(DEFAULT_SOCKET) else None,
        help="Unix socket path (Linux). Leave unset on Windows/macOS.",
    )


def connect(args, with_database=True):
    """Open a connection using the options from add_connection_args()."""
    kwargs = {"user": args.user, "password": args.password}
    if args.socket_path:
        kwargs["unix_socket"] = args.socket_path
    else:
        kwargs["host"] = args.host
        kwargs["port"] = args.port
    if with_database:
        kwargs["database"] = args.target_db
    return mysql.connector.connect(**kwargs)
