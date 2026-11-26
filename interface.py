"""Bar POS and inventory interface.

Run:
    python interface.py --password YOUR_MYSQL_PASSWORD

Screens
  1. Login           - 4-digit passcode (everyone)
  2. POS             - open tabs, add / remove drinks, COMP tab; manager can "Record Night"
  3. Night Close-out - manager enters end-of-night bottle counts/weights and sees the
                       expected-vs-actual pour (variance) report
  4. Admin           - manager adds / edits / deletes stock, menu items and employees

All SQL lives in bar_db.py. This file only builds windows and reacts to clicks.
"""
import argparse
import sys
from datetime import date, datetime

try:
    import FreeSimpleGUI as sg      # free copy of PySimpleGUI 4:  pip install FreeSimpleGUI
except ImportError:
    import PySimpleGUI as sg        # fallback if that is what is installed

import bar_db
from bar_db import Error
from db_connect import add_connection_args

COMP = "COMP"                       # the permanent comp tab (spills / drinks on the house)
CATEGORIES = [("beer", "Beers"), ("mix_drink", "Mixed Drinks"), ("shot", "Shots"), ("wine", "Wine")]
DRINK_TYPES = [key for key, _ in CATEGORIES]
STOCK_TYPES = ["beer", "wine", "liquor"]
ROLES = ["bar_tender", "manager"]


# ----------------------------------------------------------------- helpers
def db_call(fn, *args, hint=None):
    """Run a bar_db function. On a database error show a popup and return (False, None)."""
    try:
        return True, fn(*args)
    except Error as e:
        message = f"{hint}\n\n(Details: {e})" if hint else f"Database error:\n\n{e}"
        sg.popup_error(message, title="Database error")
        return False, None


def fmt(x):
    """12.50 -> '12.5', 25.0 -> '25', None -> '0'."""
    if x is None:
        return "0"
    return f"{float(x):.2f}".rstrip("0").rstrip(".") or "0"


def valid_date(text):
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def to_int(text, label, required=True):
    text = str(text).strip()
    if text == "":
        if required:
            raise ValueError(f"{label} is required.")
        return None
    try:
        value = int(text)
    except ValueError:
        raise ValueError(f"{label} must be a whole number.")
    if value < 0:
        raise ValueError(f"{label} cannot be negative.")
    return value


def to_float(text, label, required=True):
    text = str(text).strip()
    if text == "":
        if required:
            raise ValueError(f"{label} is required.")
        return None
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"{label} must be a number.")
    if value < 0:
        raise ValueError(f"{label} cannot be negative.")
    return value


def selected_row(values, key, rows):
    """The dict behind the row the user clicked in a Table (or None)."""
    picked = values.get(key)
    if picked and picked[0] < len(rows):
        return rows[picked[0]]
    return None


# ------------------------------------------------------------- tab state
# Tabs live in memory until a manager presses "Record Night". `state` survives log out / log in,
# so a bartender can hand the bar over to the manager without losing the night's tabs.
def new_tab(owner_id=None, is_comp=False):
    return {"owner_id": owner_id, "opened": datetime.now(), "is_comp": is_comp, "items": {}}


def new_state():
    return {"tabs": {COMP: new_tab(is_comp=True)}}


def item_label(item):
    return item["base"] + (f" x{item['qty']}" if item["qty"] > 1 else "")


def build_payload(state, fallback_employee_id):
    """Turn the in-memory tabs into what bar_db.record_sales() expects (empty tabs are left out)."""
    payload = []
    for name, tab in state["tabs"].items():
        if not tab["items"]:
            continue
        payload.append({
            "name": name,
            "employee_id": tab["owner_id"] or fallback_employee_id,
            "opened": tab["opened"],
            "is_comp": tab["is_comp"],
            "items": [{"menu_id": it["menu_id"], "stock_id": it["stock_id"], "qty": it["qty"]}
                      for it in tab["items"].values()],
        })
    return payload


# ------------------------------------------------------------------ login
def login(conn):
    """Return {'employee_id', 'employee_name', 'employee_role'} or None if the window is closed."""
    sg.theme('Black')
    layout = [
        [sg.VPush()],
        [sg.Push(), sg.Text("Enter Passcode", font=("Helvetica", 12)), sg.Push()],
        [sg.Push(), sg.Input(key="-PIN-", password_char='*', size=(10, 1), font=("Helvetica", 16),
                             enable_events=True, justification="center"), sg.Push()],
        [sg.Push(), sg.Text("", key='-STATUS-', font=("Helvetica", 10), text_color="gray"), sg.Push()],
        [sg.VPush()],
    ]
    window = sg.Window('Login', layout, size=(600, 400), finalize=True)
    window['-PIN-'].set_focus()
    user = None
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event == 'Exit':
            break
        if event == '-PIN-':
            current = values['-PIN-']
            digits = ''.join(ch for ch in current if ch.isdigit())[:4]
            if digits != current:
                window['-PIN-'].update(digits)
            if len(digits) == 4:
                window['-STATUS-'].update("Verifying")
                ok, found = db_call(bar_db.verify_passcode, conn, digits)
                if ok and found:
                    user = found
                    break
                window['-PIN-'].update('')
                window['-STATUS-'].update('Wrong Passcode. Try Again')
    window.close()
    return user


# -------------------------------------------------------------------- POS
def pick_one(title, options):
    """Small popup: choose one entry from a list of strings. Returns the string or None."""
    layout = [
        [sg.Text(title)],
        [sg.Listbox(values=options, key='-PICK-', size=(30, min(len(options), 8)),
                    select_mode=sg.LISTBOX_SELECT_MODE_SINGLE)],
        [sg.Button('OK'), sg.Button('Cancel')],
    ]
    window = sg.Window('Choose', layout, modal=True, finalize=True)
    choice = None
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            break
        if event == 'OK' and values['-PICK-']:
            choice = values['-PICK-'][0]
            break
    window.close()
    return choice


def choose_bottle(menu_item):
    """Which bottle was poured? Returns (stock_id, stock_name), (None, None) if the item has
    no bottles linked, or None if the bartender cancelled."""
    options = menu_item["options"]
    if not options:
        return (None, None)
    if len(options) == 1:
        return options[0]
    names = [name for _, name in options]
    picked = pick_one(f'Which bottle for {menu_item["name"]}?', names)
    if picked is None:
        return None
    return next(opt for opt in options if opt[1] == picked)


def pos_screen(conn, user, state):
    """The tab screen. Returns 'logout', 'closeout', 'admin' or 'quit'."""
    sg.theme('Black')
    is_manager = user["employee_role"] == "manager"
    ok, menu = db_call(bar_db.get_menu, conn)
    if not ok:
        return 'quit'
    menu_by_name = {m["name"]: m for m in menu}

    left_col = [
        [sg.Text(f'Logged in: {user["employee_name"]} ({user["employee_role"]})')],
        [sg.Text('New tab name'), sg.Input(key='-TAB-NAME-', expand_x=True),
         sg.Button('Add Tab', key='-ADD-TAB-', bind_return_key=True)],
        [sg.Text('Open Tabs')],
        [sg.Listbox(values=list(state["tabs"]), key='-TAB-LIST-', size=(40, 8),
                    enable_events=True, expand_x=True, expand_y=True)],
        [sg.Button('Remove Tab', key='-REMOVE-TAB-'), sg.Text('Selected tab:'),
         sg.Text('None', key='-SELECTED-TAB-', size=(20, 1))],
        [sg.Text('', key='-TAB-STATUS-', size=(55, 1))],
        [sg.Text('Items on selected tab'), sg.Button('Add Item', key='-ADD-ITEM-'),
         sg.Button('Remove Item', key='-REMOVE-ITEM-')],
        [sg.Listbox(values=[], key='-TAB-ITEMS-', size=(40, 10), expand_x=True, expand_y=True)],
        [sg.Text('Selected drink:'), sg.Text('None', key='-SELECTED-ITEM-', size=(20, 1)),
         sg.Push(), sg.Text('Tab total: $0.00', key='-TAB-TOTAL-', size=(28, 1))],
    ]

    frames, list_keys = [], []
    for drink_type, title in CATEGORIES:
        names = [m["name"] for m in menu if m["type"] == drink_type]
        if names:
            list_keys.append(f'-LIST-{drink_type}-')
            frames.append(sg.Frame(title, [[sg.Listbox(values=names, key=list_keys[-1], size=(18, 12),
                                                       enable_events=True)]],
                                   expand_x=True, expand_y=True))
    right_col = [frames] if frames else [[sg.Text('No menu items yet. A manager can add some under Admin.')]]

    bottom = [
        sg.Button('Record Night', key='-RECORD-', disabled=not is_manager),
        sg.Button('Night Close-out', key='-CLOSEOUT-', disabled=not is_manager),
        sg.Button('Admin', key='-ADMIN-', disabled=not is_manager),
        sg.Push(),
        sg.Button('Log out', key='-LOGOUT-'),
    ]
    layout = [[sg.Column(left_col, expand_x=True, expand_y=True),
               sg.Column(right_col, expand_x=True, expand_y=True)],
              bottom]
    window = sg.Window('POS', layout, size=(1100, 700), resizable=True, finalize=True)

    selected_tab = None
    selected_drink = None
    label_to_key = {}

    def status(text):
        window['-TAB-STATUS-'].update(text)

    def refresh_items():
        """Redraw the item list and total for the selected tab."""
        label_to_key.clear()
        labels, total = [], 0.0
        tab = state["tabs"].get(selected_tab)
        if tab:
            for key, item in tab["items"].items():
                label = item_label(item)
                label_to_key[label] = key
                labels.append(label)
                total += item["price"] * item["qty"]
        window['-TAB-ITEMS-'].update(values=labels)
        if tab and tab["is_comp"]:
            window['-TAB-TOTAL-'].update('Tab total: $0.00 (comp, no charge)')
        else:
            window['-TAB-TOTAL-'].update('Tab total: $%.2f' % total)

    def refresh_tabs():
        window['-TAB-LIST-'].update(values=list(state["tabs"]))
        window['-SELECTED-TAB-'].update(selected_tab or 'None')
        refresh_items()

    action = 'quit'
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            action = 'quit'
            break

        if event == '-ADD-TAB-':                                   # ---- add tab
            name = values['-TAB-NAME-'].strip()
            if not name:
                status('Enter a name for the tab.')
            elif len(name) > 30:
                status('Tab names can be at most 30 characters.')
            elif name.casefold() in {n.casefold() for n in state["tabs"]}:
                status('A tab with that name already exists.')
            else:
                state["tabs"][name] = new_tab(owner_id=user["employee_id"])
                window['-TAB-NAME-'].update('')
                refresh_tabs()
                status(f'Created tab: {name}')

        elif event == '-REMOVE-TAB-':                              # ---- remove tab (#1)
            if selected_tab is None:
                status('Select a tab to remove.')
            elif selected_tab == COMP:
                status('The COMP tab is permanent and cannot be removed.')
            else:
                count = len(state["tabs"][selected_tab]["items"])
                if count and sg.popup_yes_no(f'Remove tab "{selected_tab}" and its {count} item(s)?',
                                             title='Remove tab') != 'Yes':
                    continue
                del state["tabs"][selected_tab]
                removed, selected_tab, selected_drink = selected_tab, None, None
                window['-SELECTED-ITEM-'].update('None')
                refresh_tabs()
                status(f'Removed tab: {removed}')

        elif event == '-TAB-LIST-' and values['-TAB-LIST-']:       # ---- pick a tab
            selected_tab = values['-TAB-LIST-'][0]
            window['-SELECTED-TAB-'].update(selected_tab)
            refresh_items()
            status('')

        elif isinstance(event, str) and event.startswith('-LIST-') and values[event]:   # ---- pick a drink
            selected_drink = values[event][0]
            for key in list_keys:
                if key != event:
                    window[key].update(set_to_index=[])
            window['-SELECTED-ITEM-'].update(selected_drink)

        elif event == '-ADD-ITEM-':                                # ---- add drink to tab
            if selected_tab is None:
                status('Select a tab before adding an item.')
            elif selected_drink is None:
                status('Select a drink before adding it.')
            else:
                menu_item = menu_by_name[selected_drink]
                choice = choose_bottle(menu_item)
                if choice is None:
                    status('Cancelled.')
                    continue
                stock_id, stock_name = choice
                tab = state["tabs"][selected_tab]
                key = (menu_item["menu_id"], stock_id)
                if key in tab["items"]:
                    tab["items"][key]["qty"] += 1
                else:
                    base = menu_item["name"]
                    if len(menu_item["options"]) > 1:
                        base += f" [{stock_name}]"
                    tab["items"][key] = {"menu_id": menu_item["menu_id"], "stock_id": stock_id,
                                         "base": base, "price": menu_item["price"], "qty": 1}
                if tab["is_comp"]:
                    tab["owner_id"] = user["employee_id"]
                refresh_items()
                status(f'Added {selected_drink} to {selected_tab}.')

        elif event == '-REMOVE-ITEM-':                             # ---- remove one drink (#2)
            chosen = values['-TAB-ITEMS-']
            if selected_tab is None or not chosen:
                status('Select an item on the tab to remove.')
            else:
                items = state["tabs"][selected_tab]["items"]
                key = label_to_key.get(chosen[0])
                if key in items:
                    items[key]["qty"] -= 1
                    if items[key]["qty"] <= 0:
                        del items[key]
                refresh_items()
                status('Removed one item.')

        elif event == '-RECORD-':                                  # ---- record the night (#4-#7)
            if not is_manager:
                status('Only a manager can record the night.')
                continue
            payload = build_payload(state, user["employee_id"])
            if not payload:
                status('Nothing to record: no tab has any items yet.')
                continue
            if sg.popup_yes_no(f'Record {len(payload)} tab(s) to the database and clear them?',
                               title='Record night') != 'Yes':
                continue
            ok, written = db_call(bar_db.record_sales, conn, payload)
            if ok:
                state["tabs"] = {COMP: new_tab(is_comp=True)}
                selected_tab = None
                refresh_tabs()
                status(f'Recorded {written} tab(s).')
                sg.popup(f'Recorded {written} tab(s) to the database.', title='Saved')

        elif event == '-CLOSEOUT-' and is_manager:
            action = 'closeout'
            break
        elif event == '-ADMIN-' and is_manager:
            action = 'admin'
            break
        elif event == '-LOGOUT-':
            action = 'logout'
            break

    window.close()
    return action


# ------------------------------------------------------- night close-out
def parse_counts(values, stock):
    """Read the count boxes. Returns (counts, problems)."""
    counts, problems = [], []
    for s in stock:
        sid, name = s["stock_id"], s["stock_name"]
        try:
            bottles = to_int(values[f'-BC-{sid}-'], 'Bottles')
            if s["item_type"] == "beer":
                oz = 0.0
            else:
                oz = to_float(values[f'-OZ-{sid}-'], 'Open ounces', required=False) or 0.0
        except ValueError as e:
            problems.append(f'{name}: {e}')
            continue
        if s["bottle_size_oz"] and oz >= s["bottle_size_oz"]:
            problems.append(f'{name}: open ounces must be less than the bottle size ({s["bottle_size_oz"]} oz).')
            continue
        counts.append({"stock_id": sid, "bottle_count": bottles, "open_bottle_oz": oz})
    return counts, problems


def report_rows(report):
    return [[r["name"], fmt(r["open"]), fmt(r["close"]), fmt(r["used"]), fmt(r["expected"]),
             fmt(r["comps"]), f'{r["variance"]:+.2f}',
             '' if r["pct"] is None else f'{r["pct"]:+.1f}%', r["flag"]] for r in report]


def closeout_screen(conn, user):
    """Manager enters the night's counts (bottles + ounces left in the open bottle) and sees
    expected vs actual pour."""
    sg.theme('Black')
    ok, stock = db_call(bar_db.list_stock, conn)
    if not ok:
        return

    header = [sg.Text('Item', size=(16, 1)), sg.Text('Type', size=(8, 1)), sg.Text('System', size=(12, 1)),
              sg.Text('Bottles', size=(8, 1)), sg.Text('Open oz', size=(8, 1))]
    rows = [header]
    for s in stock:
        sid = s["stock_id"]
        rows.append([
            sg.Text(s["stock_name"], size=(16, 1)),
            sg.Text(s["item_type"], size=(8, 1)),
            sg.Text(f'{s["bottle_count"]} / {fmt(s["open_bottle_oz"])}', key=f'-SYS-{sid}-', size=(12, 1)),
            sg.Input(str(s["bottle_count"] or 0), key=f'-BC-{sid}-', size=(8, 1)),
            sg.Input(fmt(s["open_bottle_oz"]), key=f'-OZ-{sid}-', size=(8, 1),
                     disabled=(s["item_type"] == "beer")),
        ])

    headings = ['Item', 'Open', 'Close', 'Used', 'Expected', 'Comps', 'Variance', 'Var %', 'Status']
    layout = [
        [sg.Text('Night date (YYYY-MM-DD):'), sg.Input(date.today().isoformat(), key='-NIGHT-', size=(12, 1))],
        [sg.Text('Count what is on the shelf. "Open oz" = ounces left in the opened bottle (weigh it).')],
        [sg.Column(rows, scrollable=True, vertical_scroll_only=True, size=(600, 260))],
        [sg.Button('Save Counts & Show Report', key='-SAVE-'),
         sg.Button('Show Report Only', key='-SHOW-'), sg.Button('Close', key='-CLOSE-')],
        [sg.Text('', key='-MESSAGE-', size=(80, 1))],
        [sg.Table(values=[], headings=headings, key='-REPORT-TABLE-', auto_size_columns=False,
                  col_widths=[16, 8, 8, 8, 9, 7, 9, 8, 8], num_rows=11, justification='right',
                  expand_x=True)],
    ]
    window = sg.Window('Night Close-out', layout, modal=True, finalize=True)

    def show_report(night):
        ok, report = db_call(bar_db.variance_report, conn, night)
        if not ok:
            return
        window['-REPORT-TABLE-'].update(values=report_rows(report))
        if not report:
            window['-MESSAGE-'].update(f'No counts saved for {night} yet.')
        else:
            flagged = sum(1 for r in report if r["flag"] == "CHECK")
            window['-MESSAGE-'].update(
                f'{night}: {flagged} of {len(report)} items flagged CHECK. '
                f'Variance = used - expected (positive = more poured than rung up).')

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, '-CLOSE-'):
            break
        night = values['-NIGHT-'].strip()
        if not valid_date(night):
            sg.popup_error('Enter the date as YYYY-MM-DD, for example 2026-11-24.', title='Bad date')
            continue

        if event == '-SHOW-':
            show_report(night)

        elif event == '-SAVE-':
            counts, problems = parse_counts(values, stock)
            if problems:
                sg.popup_error('Please fix these first:\n\n' + '\n'.join(problems), title='Check the counts')
                continue
            ok, sales_n = db_call(bar_db.sales_count_for_date, conn, night)
            if not ok:
                continue
            if sales_n == 0 and sg.popup_yes_no(
                    f'No sales are recorded for {night}, so every pour will look like a loss.\n'
                    'Record the night on the POS screen first.\n\nSave the counts anyway?',
                    title='No sales found') != 'Yes':
                continue
            ok, _ = db_call(bar_db.save_close_counts, conn, night, user["employee_id"], counts)
            if ok:
                for c in counts:
                    window[f'-SYS-{c["stock_id"]}-'].update(
                        f'{c["bottle_count"]} / {fmt(c["open_bottle_oz"])}')
                show_report(night)
    window.close()


# ------------------------------------------------------------------ admin
def admin_screen(conn, user):
    """Manager screens to add / update / delete stock, menu items and employees."""
    sg.theme('Black')
    stock_tab = [
        [sg.Table(values=[], headings=['ID', 'Name', 'Type', 'Bottles', 'Size oz', 'Open oz', 'Serving oz'],
                  key='-S-TABLE-', auto_size_columns=False, col_widths=[4, 18, 8, 8, 8, 8, 10],
                  num_rows=9, enable_events=True, select_mode=sg.TABLE_SELECT_MODE_BROWSE, expand_x=True)],
        [sg.Text('Name', size=(10, 1)), sg.Input(key='-S-NAME-', size=(18, 1)), sg.Text('Type'),
         sg.Combo(STOCK_TYPES, default_value='liquor', key='-S-TYPE-', readonly=True, size=(8, 1))],
        [sg.Text('Bottles', size=(10, 1)), sg.Input(key='-S-BOTTLES-', size=(8, 1)), sg.Text('Size oz'),
         sg.Input(key='-S-SIZE-', size=(8, 1)), sg.Text('Open oz'), sg.Input(key='-S-OPEN-', size=(8, 1)),
         sg.Text('Serving oz'), sg.Input(key='-S-SERVING-', size=(8, 1))],
        [sg.Button('Add', key='-S-ADD-'), sg.Button('Update Selected', key='-S-UPDATE-'),
         sg.Button('Delete Selected', key='-S-DELETE-'), sg.Text('   Delivery: +'),
         sg.Input('6', key='-S-DELIVERY-', size=(5, 1)), sg.Button('Receive Delivery', key='-S-RECEIVE-')],
        [sg.Text('Beer: leave Size and Serving blank. Liquor/wine: Size = ounces per bottle.')],
    ]
    menu_tab = [
        [sg.Table(values=[], headings=['ID', 'Name', 'Type', 'Price', 'Poured from'], key='-M-TABLE-',
                  auto_size_columns=False, col_widths=[4, 22, 10, 8, 30], num_rows=9, enable_events=True,
                  select_mode=sg.TABLE_SELECT_MODE_BROWSE, expand_x=True)],
        [sg.Text('Name'), sg.Input(key='-M-NAME-', size=(20, 1)), sg.Text('Type'),
         sg.Combo(DRINK_TYPES, default_value='beer', key='-M-TYPE-', readonly=True, size=(10, 1)),
         sg.Text('Price $'), sg.Input(key='-M-PRICE-', size=(8, 1))],
        [sg.Text('Poured from\n(Ctrl-click for several)'),
         sg.Listbox(values=[], key='-M-OPTS-', size=(26, 6), select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE)],
        [sg.Button('Add', key='-M-ADD-'), sg.Button('Update Selected', key='-M-UPDATE-'),
         sg.Button('Delete Selected', key='-M-DELETE-')],
    ]
    emp_tab = [
        [sg.Table(values=[], headings=['ID', 'Name', 'Role', 'Passcode'], key='-E-TABLE-',
                  auto_size_columns=False, col_widths=[4, 22, 12, 10], num_rows=9, enable_events=True,
                  select_mode=sg.TABLE_SELECT_MODE_BROWSE, expand_x=True)],
        [sg.Text('Name'), sg.Input(key='-E-NAME-', size=(20, 1)), sg.Text('Role'),
         sg.Combo(ROLES, default_value='bar_tender', key='-E-ROLE-', readonly=True, size=(10, 1)),
         sg.Text('Passcode (4 digits)'), sg.Input(key='-E-PASS-', size=(6, 1))],
        [sg.Button('Add', key='-E-ADD-'), sg.Button('Update Selected', key='-E-UPDATE-'),
         sg.Button('Delete Selected', key='-E-DELETE-')],
    ]
    layout = [[sg.TabGroup([[sg.Tab('Stock', stock_tab), sg.Tab('Menu', menu_tab),
                             sg.Tab('Employees', emp_tab)]])],
              [sg.Text('', key='-ADMIN-MSG-', size=(70, 1)), sg.Push(), sg.Button('Close', key='-CLOSE-')]]
    window = sg.Window('Admin', layout, modal=True, finalize=True)

    stock_rows, menu_rows, emp_rows = [], [], []

    def say(text):
        window['-ADMIN-MSG-'].update(text)

    def reload_stock():
        nonlocal stock_rows
        ok, rows = db_call(bar_db.list_stock, conn)
        if ok:
            stock_rows = rows
            window['-S-TABLE-'].update(values=[
                [r["stock_id"], r["stock_name"], r["item_type"], r["bottle_count"],
                 '' if r["bottle_size_oz"] is None else r["bottle_size_oz"], fmt(r["open_bottle_oz"]),
                 '' if r["serving_size"] is None else fmt(r["serving_size"])] for r in rows])
            window['-M-OPTS-'].update(values=[r["stock_name"] for r in rows])

    def reload_menu():
        nonlocal menu_rows
        ok, rows = db_call(bar_db.get_menu, conn)
        if ok:
            menu_rows = rows
            window['-M-TABLE-'].update(values=[
                [r["menu_id"], r["name"], r["type"], '%.2f' % r["price"],
                 ', '.join(n for _, n in r["options"])] for r in rows])

    def reload_emps():
        nonlocal emp_rows
        ok, rows = db_call(bar_db.list_employees, conn)
        if ok:
            emp_rows = rows
            window['-E-TABLE-'].update(values=[
                [r["employee_id"], r["employee_name"], r["employee_role"], r["passcode"]] for r in rows])

    def read_stock_form(values):
        name = values['-S-NAME-'].strip()
        if not name:
            raise ValueError('Name is required.')
        item_type = values['-S-TYPE-']
        bottles = to_int(values['-S-BOTTLES-'] or 0, 'Bottles')
        size = to_int(values['-S-SIZE-'], 'Size oz', required=(item_type != 'beer'))
        open_oz = to_float(values['-S-OPEN-'] or 0, 'Open oz')
        serving = to_float(values['-S-SERVING-'], 'Serving oz', required=(item_type != 'beer'))
        if size and open_oz >= size:
            raise ValueError('Open oz must be less than the bottle size.')
        return name, item_type, bottles, size, open_oz, serving

    def read_menu_form(values):
        name = values['-M-NAME-'].strip()
        if not name:
            raise ValueError('Name is required.')
        price = to_float(values['-M-PRICE-'], 'Price')
        wanted = set(values['-M-OPTS-'])
        stock_ids = [r["stock_id"] for r in stock_rows if r["stock_name"] in wanted]
        if not stock_ids:
            raise ValueError('Pick at least one bottle this drink is poured from.')
        return name, values['-M-TYPE-'], price, stock_ids

    def read_emp_form(values):
        name = values['-E-NAME-'].strip()
        passcode = values['-E-PASS-'].strip()
        if not name:
            raise ValueError('Name is required.')
        if not (len(passcode) == 4 and passcode.isdigit()):
            raise ValueError('Passcode must be exactly 4 digits.')
        return name, values['-E-ROLE-'], passcode

    reload_stock()
    reload_menu()
    reload_emps()

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, '-CLOSE-'):
            break
        try:
            # ---------------- stock
            if event == '-S-TABLE-':
                row = selected_row(values, '-S-TABLE-', stock_rows)
                if row:
                    window['-S-NAME-'].update(row["stock_name"])
                    window['-S-TYPE-'].update(row["item_type"])
                    window['-S-BOTTLES-'].update(str(row["bottle_count"]))
                    window['-S-SIZE-'].update('' if row["bottle_size_oz"] is None else str(row["bottle_size_oz"]))
                    window['-S-OPEN-'].update(fmt(row["open_bottle_oz"]))
                    window['-S-SERVING-'].update('' if row["serving_size"] is None else fmt(row["serving_size"]))
            elif event == '-S-ADD-':
                ok, _ = db_call(bar_db.add_stock, conn, *read_stock_form(values))
                if ok:
                    reload_stock()
                    say('Stock item added.')
            elif event == '-S-UPDATE-':
                row = selected_row(values, '-S-TABLE-', stock_rows)
                if not row:
                    say('Select a stock row first.')
                else:
                    ok, _ = db_call(bar_db.update_stock, conn, row["stock_id"], *read_stock_form(values))
                    if ok:
                        reload_stock()
                        reload_menu()
                        say('Stock item updated.')
            elif event == '-S-DELETE-':
                row = selected_row(values, '-S-TABLE-', stock_rows)
                if not row:
                    say('Select a stock row first.')
                elif sg.popup_yes_no(f'Delete {row["stock_name"]}?', title='Delete stock') == 'Yes':
                    ok, _ = db_call(bar_db.delete_stock, conn, row["stock_id"],
                                    hint="This item has sales or count history, so it can't be deleted.")
                    if ok:
                        reload_stock()
                        reload_menu()
                        say('Stock item deleted.')
            elif event == '-S-RECEIVE-':
                row = selected_row(values, '-S-TABLE-', stock_rows)
                if not row:
                    say('Select a stock row first.')
                else:
                    amount = to_int(values['-S-DELIVERY-'], 'Delivery bottles')
                    ok, _ = db_call(bar_db.receive_delivery, conn, row["stock_id"], amount)
                    if ok:
                        reload_stock()
                        say(f'Added {amount} to {row["stock_name"]}.')

            # ---------------- menu
            elif event == '-M-TABLE-':
                row = selected_row(values, '-M-TABLE-', menu_rows)
                if row:
                    window['-M-NAME-'].update(row["name"])
                    window['-M-TYPE-'].update(row["type"])
                    window['-M-PRICE-'].update('%.2f' % row["price"])
                    window['-M-OPTS-'].set_value([n for _, n in row["options"]])
            elif event == '-M-ADD-':
                ok, _ = db_call(bar_db.add_menu_item, conn, *read_menu_form(values))
                if ok:
                    reload_menu()
                    say('Menu item added.')
            elif event == '-M-UPDATE-':
                row = selected_row(values, '-M-TABLE-', menu_rows)
                if not row:
                    say('Select a menu row first.')
                else:
                    name, drink_type, price, stock_ids = read_menu_form(values)
                    ok, _ = db_call(bar_db.update_menu_item, conn, row["menu_id"], name, drink_type,
                                    price, stock_ids,
                                    hint="A bottle that past sales used can't be removed from this drink.")
                    if ok:
                        reload_menu()
                        say('Menu item updated.')
            elif event == '-M-DELETE-':
                row = selected_row(values, '-M-TABLE-', menu_rows)
                if not row:
                    say('Select a menu row first.')
                elif sg.popup_yes_no(f'Delete {row["name"]}?', title='Delete menu item') == 'Yes':
                    ok, _ = db_call(bar_db.delete_menu_item, conn, row["menu_id"],
                                    hint="This drink appears on past sales, so it can't be deleted.")
                    if ok:
                        reload_menu()
                        say('Menu item deleted.')

            # ---------------- employees
            elif event == '-E-TABLE-':
                row = selected_row(values, '-E-TABLE-', emp_rows)
                if row:
                    window['-E-NAME-'].update(row["employee_name"])
                    window['-E-ROLE-'].update(row["employee_role"])
                    window['-E-PASS-'].update(row["passcode"])
            elif event == '-E-ADD-':
                ok, _ = db_call(bar_db.add_employee, conn, *read_emp_form(values),
                                hint="Could not add the employee. Is that passcode already taken?")
                if ok:
                    reload_emps()
                    say('Employee added.')
            elif event == '-E-UPDATE-':
                row = selected_row(values, '-E-TABLE-', emp_rows)
                if not row:
                    say('Select an employee row first.')
                else:
                    ok, _ = db_call(bar_db.update_employee, conn, row["employee_id"], *read_emp_form(values),
                                    hint="Could not update the employee. Is that passcode already taken?")
                    if ok:
                        reload_emps()
                        say('Employee updated.')
            elif event == '-E-DELETE-':
                row = selected_row(values, '-E-TABLE-', emp_rows)
                if not row:
                    say('Select an employee row first.')
                elif row["employee_id"] == user["employee_id"]:
                    say('You cannot delete the account you are logged in with.')
                elif sg.popup_yes_no(f'Delete {row["employee_name"]}?', title='Delete employee') == 'Yes':
                    ok, _ = db_call(bar_db.delete_employee, conn, row["employee_id"],
                                    hint="This employee has recorded sales or counts, so can't be deleted.")
                    if ok:
                        reload_emps()
                        say('Employee deleted.')
        except ValueError as e:                       # bad text in a form box
            sg.popup_error(str(e), title='Check the form')
    window.close()


# ------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description="Bar POS and inventory interface.")
    add_connection_args(parser)
    parser.add_argument("--device", type=str, default=None, help=argparse.SUPPRESS)  # old flag, ignored
    args = parser.parse_args()

    try:
        conn = bar_db.open_connection(args)
    except Error as e:
        print(f"Could not connect to MySQL: {e}\n"
              "Check that the MySQL server is running, that --password is right, and that you "
              "ran recreate_db.py, populate_db.py and populate_sales.py.")
        sys.exit(1)

    state = new_state()
    user = login(conn)
    while user is not None:
        action = pos_screen(conn, user, state)
        if action == 'closeout':
            closeout_screen(conn, user)
        elif action == 'admin':
            admin_screen(conn, user)
        elif action == 'logout':
            user = login(conn)
        else:
            break
    conn.close()


if __name__ == "__main__":
    main()
