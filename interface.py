import PySimpleGUI as sg
import mysql.connector
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--device", type=str, choices=["unix", "windows", "mac"], default="unix")
parser.add_argument("--password", type=str, default="")
parser.add_argument("--socket_path", type=str, default="/var/run/mysqld/mysqld.sock")

args = parser.parse_args()

if args.device == "unix":
    connection = mysql.connector.connect(
            user="root", 
            password=args.password,
            database="Bar_Database",
            unix_socket=args.socket_path)
elif args.device == "windows":
    connection = mysql.connector.connect()
elif args.device == "mac":
    connection = mysql.connector.connect()

cursor = connection.cursor()
usr_passcode = ''

def verify_passcode(submission) -> int:
    verify_query = f"SELECT employee_id FROM Employees WHERE passcode = %s"
    try:
        cursor.execute(verify_query, (submission, ))
        result = cursor.fetchone()
    except mysql.connector.Error as e:
        print(f"DB error: {e}")
    if result is None:
        return None
    return result[0]

def get_menu_items_by(drink_type : str) -> list:
    query = f"SELECT drink_name FROM Menu_Items WHERE drink_type = %s"
    try:
        cursor.execute(query, (drink_type, ))
        result = cursor.fetchall()
    except mysql.connector.Error as e:
        print(f"DB Error: {e}")
        return []
    if result is None:
        return []
    result = [row[0] for row in result]
    return result

def login() -> int:
    sg.theme('Black')
    layout = [
        [sg.VPush()],
        [
            [sg.Push(), sg.Text("Enter Passcode", font=("Helvetica", 12)), sg.Push()],
            [sg.Push(), sg.Input(key="-PIN-", password_char='*', size=(10, 1), font=("Helvetica", 16), enable_events=True, justification="center"), sg.Push()],
            [sg.Push(), sg.Text("", key='-STATUS-', font=("Helvetica", 10), text_color="gray"), sg.Push()],
        ],
        [sg.VPush()]
    ]
    
    window = sg.Window('login', layout, size=(600, 400), finalize=True)
    window['-PIN-'].set_focus()
    print(window['-PIN-'].get())
    authenticated = False

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event == 'Exit':
            break
        if event == '-PIN-':
            current_val = values['-PIN-']
            filtered_val = ''.join([char for char in current_val if char.isdigit()])
            if len(filtered_val) > 4:
                filtered_val = filtered_val[:4]
            if filtered_val != current_val:
                window['-PIN-'].update(filtered_val)
            if len(filtered_val) == 4:
                window['-STATUS-'].update("Verifying")
                authenticated_id = verify_passcode(window['-PIN-'].get())
                if authenticated_id is not None:
                    print('Access Granted Welcome to the system!')
                    
                    break
                else:
                    window['-PIN-'].update('')
                    window['-STATUS-'].update('Wrong Passcode. Try Again')
    window.close()
    return authenticated_id

def get_tabs_by_user(employee_id: int) -> list[str]:
    tabs_query = "SELECT sale_name FROM Sales WHERE employee_id = %s"
    try:
        cursor.execute(tabs_query, (employee_id, ))
        result = cursor.fetchall()
        
        return [row[0] for row in result]
    except mysql.connection.Error as e:
        print(f"DB Error: {e}")
        return []

def get_sale_items(employee_id: int, names: list[str]) -> dict[str, dict[str, int]]:
    tab_items = {name: {} for name in names}
    items_query = """
        SELECT Sales.sale_name, Menu_Items.drink_name, Sale_Menu_Items.quantity
        FROM Sales
        LEFT JOIN Sale_Menu_Items ON Sales.sale_id = Sale_Menu_Items.sale_id
        LEFT JOIN Menu_Items ON Sale_Menu_Items.menu_id = Menu_Items.menu_id
        WHERE Sales.employee_id = %s
        ORDER BY Sales.sale_id, Menu_Items.drink_name
    """
    try:
        cursor.execute(items_query, (employee_id,))
        for sale_name, drink_name, quantity in cursor.fetchall():
            if sale_name in tab_items and drink_name is not None:
                tab_items[sale_name][drink_name] = quantity
    except mysql.connector.Error as e:
        print(f"DB Error: {e}")
    return tab_items

def add_drink_to_sale(employee_id: int, sale_name: str, drink_name: str) -> None:
    cursor.execute(
        """
        SELECT sale_id FROM Sales
        WHERE employee_id = %s AND sale_name = %s
        ORDER BY sale_id DESC
        LIMIT 1
        """,
        (employee_id, sale_name),
    )
    sale = cursor.fetchone()
    if sale is None:
        raise ValueError(f"Tab not found: {sale_name}")

    cursor.execute(
        "SELECT menu_id FROM Menu_Items WHERE drink_name = %s LIMIT 1",
        (drink_name,),
    )
    menu_item = cursor.fetchone()
    if menu_item is None:
        raise ValueError(f"Menu item not found: {drink_name}")

    cursor.execute(
        """
        INSERT INTO Sale_Menu_Items (sale_id, menu_id, quantity)
        VALUES (%s, %s, 1)
        ON DUPLICATE KEY UPDATE quantity = quantity + 1
        """,
        (sale[0], menu_item[0]),
    )
    connection.commit()

def sales_interface(employee_id : int):
    sg.theme('Black')
    tabs = get_tabs_by_user(employee_id)
    tab_items = get_sale_items(employee_id, tabs)
    selected_tab = None
    selected_drink = None
    left_col = [
        [sg.Text('New tab name'),sg.Input(key='-TAB-NAME-', expand_x=True),sg.Button('Add Tab', key='-ADD-TAB-'),],
        [sg.Text('Open Tabs')],
        [sg.Listbox(values=tabs, key='-TAB-LIST-', size=(40, 12), enable_events=True, expand_x=True, expand_y=True,)],
        [sg.Text('Selected tab:'),sg.Text('None', key='-SELECTED-TAB-'),],
        [sg.Text('', key='-TAB-STATUS-')],
        [sg.Text('Items on selected tab'), sg.Button('Add Item', key='-ADD-ITEM-')],
        [sg.Listbox(values=[], key='-TAB-ITEMS-', size=(40, 12), expand_x=True, expand_y=True)],
        [sg.Text('Selected Item:'), sg.Text('None', key='-SELECTED-ITEM-')]
    ]

    beers = get_menu_items_by("beer")
    mix = get_menu_items_by("mix_drink")
    shots = get_menu_items_by("shot")
    seltzers = []
    wines = []

    right_col = [
        [sg.VPush()],
        [
            sg.Push(),
            sg.Frame("Beers", [
                [sg.Listbox(values=beers, key='-BEER-LIST-', size=(14, 10), enable_events=True)]
                ], expand_x=True, expand_y=True),
            sg.Push(),
            sg.Frame("Mixed Drinks", [
                [sg.Listbox(values=mix, key='-MIX-LIST-', size=(14, 10), enable_events=True)]
                ], expand_x=True, expand_y=True),
            sg.Push(),
            sg.Frame("Shots", [
                [sg.Listbox(values=shots, key='-SHOTS-LIST-', size=(14, 10), enable_events=True)]
                ], expand_x=True, expand_y=True),
            sg.Push(),
        ],
        [
            sg.Push(),
            sg.Frame("Wines", [
                [sg.Listbox(values=wines, key='-WINE-LIST-', size=(14, 10), enable_events=True)]
            ], expand_x=True, expand_y=True),
            sg.Push(),
            sg.Frame("Seltzers", [
                [sg.Listbox(values=seltzers, key='-SELTZER-LIST-', size=(14, 10), enable_events=True)]
            ], expand_x=True, expand_y=True),
            sg.Push(),
        ],
        [sg.VPush()]
    ]
    layout = [
        [sg.Column(left_col, expand_x=True, expand_y=True), sg.Column(right_col, expand_x=True, expand_y=True)]
    ]

    window = sg.Window('POS', layout, size=(1200,800), resizable=True, finalize=True)

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break
        if event == '-ADD-TAB-':
            tab_name = values['-TAB-NAME-'].strip()
            if not tab_name:
                window['-TAB-STATUS-'].update('Enter a name for the tab.')
            elif tab_name.casefold() in {name.casefold() for name in tabs}:
                window['-TAB-STATUS-'].update('A tab with that name already exists.')
            else:
                try:
                    cursor.execute(
                        "INSERT INTO Sales (sale_name, employee_id) VALUES (%s, %s)",
                        (tab_name, employee_id),
                    )
                    connection.commit()
                except mysql.connector.Error as e:
                    connection.rollback()
                    print(f"DB Error: {e}")
                    window['-TAB-STATUS-'].update(f'Could not create tab: {e}')
                else:
                    tabs.append(tab_name)
                    tab_items[tab_name] = {}
                    window['-TAB-LIST-'].update(values=tabs)
                    window['-TAB-NAME-'].update('')
                    window['-TAB-STATUS-'].update(f'Created tab: {tab_name}')
        elif event == '-TAB-LIST-':
            selected_tabs = values.get('-TAB-LIST-', [])
            if selected_tabs:
                selected_tab = selected_tabs[0]
                selected_drink = None
                window['-SELECTED-TAB-'].update(selected_tab)
                window['-SELECTED-ITEM-'].update('None')
                items = tab_items.get(selected_tab, {})
                window['-TAB-ITEMS-'].update(values=[
                    f'{drink} x{count}' if count > 1 else drink
                    for drink, count in items.items()
                ])
                window['-TAB-STATUS-'].update('')
        elif event == '-ADD-ITEM-':
            if selected_tab is None:
                window['-TAB-STATUS-'].update('Select a tab before adding an item.')
            elif selected_drink is None:
                window['-TAB-STATUS-'].update('Select a drink before adding it.')
            else:
                try:
                    add_drink_to_sale(employee_id, selected_tab, selected_drink)
                except (mysql.connector.Error, ValueError) as e:
                    connection.rollback()
                    print(f"DB Error: {e}")
                    window['-TAB-STATUS-'].update(f'Could not save drink: {e}')
                else:
                    items = tab_items[selected_tab]
                    items[selected_drink] = items.get(selected_drink, 0) + 1
                    window['-TAB-ITEMS-'].update(values=[
                        f'{drink} x{count}' if count > 1 else drink
                        for drink, count in items.items()
                    ])
                    window['-TAB-STATUS-'].update(
                        f'Added {selected_drink} to {selected_tab}.'
                    )
        elif event in ('-BEER-LIST-', '-MIX-LIST-', '-SHOTS-LIST-') and values[event]:
            selected_drink = values[event][0]
            for list_key in ('-BEER-LIST-', '-MIX-LIST-', '-SHOTS-LIST-'):
                if list_key != event:
                    window[list_key].update(set_to_index=[])
            window['-SELECTED-ITEM-'].update(selected_drink)
    window.close()

if __name__=="__main__":
    employee_id = login()
    sales_interface(employee_id)