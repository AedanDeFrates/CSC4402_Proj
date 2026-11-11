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

def verify_passcode(submission) -> bool:
    query = f"SELECT passcode FROM Employees WHERE passcode = %s"
    try:
        cursor.execute(query, (submission, ))
        result = cursor.fetchone()
    except mysql.connector.Error as e:
        print(f"DB error: {e}")
        return False
    if result is None:
        return False
    return result[0] == submission

def login() -> bool:
    sg.theme('Black')
    layout = [
        [sg.Text("Enter Passcode", font=("Helvetica", 12))],
        [sg.Input(key="-PIN-", password_char='*', size=(10, 1), font=("Helvetica", 16), enable_events=True, justification="center")],
        [sg.Text("", key='-STATUS-', font=("Helvetica", 10), text_color="gray")]
    ]
    
    window = sg.Window('login', layout, finalize=True)
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
                if verify_passcode(window['-PIN-'].get()):
                    print('Access Granted Welcome to the system!')
                    usr_passcode = window['-PIN-'].get()
                    authenticated = True
                    break
                else:
                    window['-PIN-'].update('')
                    window['-STATUS-'].update('Wrong Passcode. Try Again')
    window.close()
    return authenticated

def sales_interface():
    sg.theme('Black')
    tabs = []
    left_col = [
        [sg.Text('New tab name'),sg.Input(key='-TAB-NAME-', expand_x=True),sg.Button('Add Tab', key='-ADD-TAB-'),],
        [sg.Text('Open Tabs')],
        [sg.Listbox(values=tabs, key='-TAB-LIST-', size=(40, 12), enable_events=True, expand_x=True, expand_y=True,)],
        [sg.Text('Selected tab:'),sg.Text('None', key='-SELECTED-TAB-'),],
        [sg.Text('', key='-TAB-STATUS-')],
    ]
    right_col = [
        [sg.Text('Items on selected tab')],
        [sg.Button('Add Item', key='-ADD-ITEM-')],
        [sg.Listbox(values=[], key='-TAB-ITEMS-', size=(40, 12), expand_x=True, expand_y=True)],
    ]
    layout = [
        [sg.Column(left_col, expand_x=True, expand_y=True), sg.Column(right_col, expand_x=True, expand_y=True)]
    ]
    window = sg.Window('POS', layout, resizable=True, finalize=True)
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
                tabs.append(tab_name)
                window['-TAB-LIST-'].update(values=tabs)
                window['-TAB-NAME-'].update('')
                window['-TAB-STATUS-'].update(f'Created tab: {tab_name}')
        elif event == '-TAB-LIST-' and values['-TAB-LIST-']:
            window['-SELECTED-TAB-'].update(values['-TAB-LIST-'][0])
            window['-TAB-ITEMS-'].update(values=[])
            window['-TAB-STATUS-'].update('')
        elif event == '-ADD-ITEM-':
            continue
    window.close()


#TODO: 1) Make POS system. 2) Add menu items to interface to easily make sales 3) Ability to make a tab and close it (finalize sale for db)

if __name__=="__main__":
    if login():
        sales_interface()
    
