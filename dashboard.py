"""Manager dashboard window backed by analytics.py."""
try:
    import FreeSimpleGUI as sg
except ImportError:
    import PySimpleGUI as sg

import analytics
from mysql.connector import Error


def _load_dashboard(conn, today):
    return {
        "today_revenue": analytics.get_total_revenue(conn, today),
        "total_revenue": analytics.get_total_revenue(conn),
        "sales_count": analytics.get_sales_count(conn, today),
        "top_drinks": analytics.get_top_selling_drinks(conn),
        "low_inventory": analytics.get_low_inventory(conn),
        "variance_alerts": analytics.get_variance_alerts(conn),
    }


def _names(items, key):
    return [item[key] for item in items] or ["None"]


def dashboard_screen(conn, today):
    """Show today's and all-time sales alongside current manager alerts."""
    sg.theme("Black")

    def refresh():
        try:
            data = _load_dashboard(conn, today)
        except Error as error:
            sg.popup_error(f"Could not load dashboard data:\n\n{error}", title="Database error")
            return

        top_drinks = [
            f'{item["drink_name"]} - {item["units_sold"]} sold (${float(item["revenue"]):,.2f})'
            for item in data["top_drinks"]
        ] or ["No paid sales recorded."]
        low_inventory = _names(data["low_inventory"], "stock_name")
        variance_alerts = [
            f'{item["name"]} - {item["variance"]:+.2f} oz'
            for item in data["variance_alerts"]
        ] or ["None"]

        window["-TODAY-"].update(f'${data["today_revenue"]:,.2f}')
        window["-TOTAL-"].update(f'${data["total_revenue"]:,.2f}')
        window["-SALES-"].update(str(data["sales_count"]))
        window["-TOP-"].update(values=top_drinks)
        window["-INVENTORY-"].update(values=low_inventory)
        window["-VARIANCE-"].update(values=variance_alerts)

    layout = [
        [sg.Text("Manager Dashboard", font=("Any", 20))],
        [sg.Text("Today's Revenue", size=(22, 1)), sg.Text("$0.00", key="-TODAY-", font=("Any", 16)),
         sg.Text("Total Revenue", size=(18, 1)), sg.Text("$0.00", key="-TOTAL-", font=("Any", 16)),
         sg.Text("Today's Sales Count", size=(20, 1)), sg.Text("0", key="-SALES-", font=("Any", 16))],
        [sg.Frame("Best Selling Drinks", [[sg.Listbox([], key="-TOP-", size=(72, 6), expand_x=True)]],
                  expand_x=True),
         sg.Frame("Inventory Alerts", [[sg.Listbox([], key="-INVENTORY-", size=(28, 6), expand_x=True)]],
                  expand_x=True)],
        [sg.Frame("Variance Alerts (latest counted night)", [
            [sg.Listbox([], key="-VARIANCE-", size=(105, 7), expand_x=True)]
        ], expand_x=True)],
        [sg.Button("Refresh", key="-REFRESH-"), sg.Push(), sg.Button("Close", key="-CLOSE-")],
    ]
    window = sg.Window("Manager Dashboard", layout, size=(1000, 550), resizable=True, modal=True,
                       finalize=True)
    refresh()
    while True:
        event, _ = window.read()
        if event in (sg.WIN_CLOSED, "-CLOSE-"):
            break
        if event == "-REFRESH-":
            refresh()
    window.close()
