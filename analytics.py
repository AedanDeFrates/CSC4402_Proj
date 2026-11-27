"""Manager reporting API backed by the shared bar_db data-access layer."""
import bar_db


def get_total_revenue(conn, night=None):
    """Return paid-sales revenue, optionally limited to a YYYY-MM-DD date."""
    return bar_db.total_revenue(conn, night)


def get_revenue_by_employee(conn):
    """Return paid tab counts and revenue for each employee."""
    return bar_db.revenue_by_employee(conn)


def get_top_selling_drinks(conn, limit=5):
    """Return the most purchased paid menu items with units sold and revenue."""
    return bar_db.top_selling_drinks(conn, limit)


def get_low_inventory(conn):
    """Return stock items below the average unopened-bottle count for their type."""
    return bar_db.low_inventory(conn)


def get_variance_alerts(conn, night=None):
    """Return flagged pour variances for a date, defaulting to the latest counted night."""
    return bar_db.variance_alerts(conn, night)


def get_sales_count(conn, night=None):
    """Return the number of recorded sales, optionally limited to a YYYY-MM-DD date."""
    return int(bar_db.sales_count_for_date(conn, night))
