import PySimpleGUI as sg
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--login_test", type=bool, default=False)

args = parser.parse_args()

def login_test():
    sg.theme('Black')
    layout = [
        [sg.Text('Enter 4-Digit Combo / PIN', font=('Helvetica', 14), justification='center', expand_x=True)],
        [sg.Input(password_char='*', size=(10, 1), font=('Helvetica', 18), key='-PIN-', justification='center', expand_x=True)],
        [sg.HorizontalSeparator()],
        [sg.Button('Submit', bind_return_key=True, expand_x=True), sg.Button('Exit', expand_x=True)]
    ]
    window = sg.Window('LOGIN', layout, finalize=True)
    CORRECT_PIN = "1234"
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event == 'Exit':
            break
        if event == 'Submit':
            entered_pin = values['-PIN-']
            if len(entered_pin) == 4 and entered_pin.isdigit():
                if entered_pin == CORRECT_PIN:
                    print('Access Granted Welcome to the system!')
                    break
                else:
                    print('Incorrect PIN. Please try again.')
                    window['-PIN-'].update('')
            else:
                print('Please enter a valid 4-digit numeric code.')
                window['-PIN-'].update('')
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