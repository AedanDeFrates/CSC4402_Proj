import PySimpleGUI as sg
import mysql.connector
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--device", type=str, choices=["unix", "windows", "mac"], default="unix")
parser.add_argument("--password", type=str, default="")
parser.add_argument("--socket_path", type=str, default="/var/run/mysqld/mysqld.sock")
parser.add_argument("--login_test", type=bool, default=False)

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

def login_test():
    sg.theme('Black')
    layout = [
        [sg.Text("Enter Passcode", font=("Helvetica", 12))],
        [sg.Input(key="-PIN-", password_char='*', size=(10, 1), font=("Helvetica", 16), enable_events=True, justification="center")],
        [sg.Text("", key='-STATUS-', font=("Helvetica", 10), text_color="gray")]
    ]
    
    window = sg.Window('login', layout, finalize=True)
    window['-PIN-'].set_focus()
    print(window['-PIN-'].get())

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
                    break
                else:
                    window['-PIN-'].update('')
                    window['-STATUS-'].update('Wrong Passcode. Try Again')
    window.close()

if __name__=="__main__":
    if args.login_test : login_test()

    sg.theme('Dark')
    sg.set_options(element_padding=(0, 0))

    layout = [[sg.Text('User:', pad=((3, 0), 0)), sg.OptionMenu(values=('User 1', 'User 2'), size=(20, 1)),
            sg.Text('0', size=(8, 1))],
            [sg.Text('Customer:', pad=((3, 0), 0)), sg.OptionMenu(values=('Customer 1', 'Customer 2'), size=(20, 1)),
            sg.Text('1', size=(8, 1))],
            [sg.Text('Notes:', pad=((3, 0), 0)),
            sg.Input(size=(44, 1), background_color='white', text_color='black')],
            [sg.Button('Start', button_color=('white', 'black')),
            sg.Button('Stop', button_color=('gray50', 'black')),
            sg.Button('Reset', button_color=('white', '#9B0023')),
            sg.Button('Submit', button_color=('gray60', 'springgreen4')),
            sg.Button('Exit', button_color=('white', '#00406B'))]]

    window = sg.Window("Borderless Window",
                    layout,
                    default_element_size=(12, 1),
                    text_justification='r',
                    auto_size_text=False,
                    auto_size_buttons=False,
                    no_titlebar=True,
                    grab_anywhere=True,
                    default_button_element_size=(12, 1))

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'):
            break
    cursor.close()
    connection.close()