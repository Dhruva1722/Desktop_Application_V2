import socket
import mss
import ctypes 
import string
import random
import lz4.frame
from PIL import Image,  ImageGrab, ImageTk
from io import BytesIO
from threading import Thread
from multiprocessing import Process, Queue, freeze_support
from pynput.mouse import Button, Controller as Mouse_controller
import tkinter as tk
from tkinter.font import Font
from tkinter import ttk
from pynput.keyboard import Key, Controller as Keyboard_controller
import random
from tkinter import messagebox
import mss
import mss.tools
import os
import time
from datetime import datetime 
import shutil
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinter import filedialog , scrolledtext
import tkinter.dnd as dnd

      
# Receive data as chunks and rebuild message.
def data_recive(socket, size_of_header, chunk_prev_message, buffer_size=65536):
    # print(socket,"--socket")
    prev_buffer_size = len(chunk_prev_message)
    headerMsg = bytes()
    # print(f'headerMsg {headerMsg}')
    if prev_buffer_size < size_of_header:
            headerMsg = socket.recv(size_of_header - prev_buffer_size)

            if len(headerMsg) != size_of_header:
                headerMsg = chunk_prev_message + headerMsg
                chunk_prev_message = bytes()

    elif prev_buffer_size >= size_of_header:
        headerMsg = chunk_prev_message[:size_of_header]
        chunk_prev_message = chunk_prev_message[size_of_header:]
    
    global msgSize,newMsg
    try:   
        msgSize = int(headerMsg.decode())
        # print(f'msgSize {msgSize}')
        newMsg = chunk_prev_message
        # print(f'newMsg {newMsg}')
        chunk_prev_message = bytes()
    except (ValueError):
        pass    

    if msgSize:
        while True:
            if len(newMsg) < msgSize:
                newMsg += socket.recv(buffer_size)
            elif len(newMsg) > msgSize:
                chunk_prev_message = newMsg[msgSize:]
                newMsg = newMsg[:msgSize]
            if len(newMsg) == msgSize:
                break
        return newMsg, chunk_prev_message
    else:
        return None

#Send data 
def send_data(socket, size_of_header, msg_data):
    msg_len = len(msg_data)
    if msg_len:
        header = f"{msg_len:<{size_of_header}}"
        # time.sleep(5)
        socket.send(bytes(header, "utf-8") + msg_data)  


def find_button(btn_code, event_Code):
    for key in btn_code.keys():
        if event_Code in key:
            return btn_code.get(key)
     
        
def simulate(mouse, keyboard, btn_code, key_map, event_Code, msg):
    if event_Code == -1:
        if len(msg) == 1:
            keyboard.press(msg)
        else:
            keyboard.press(key_map.get(msg))
    elif event_Code == -2:
        if len(msg) == 1:
            keyboard.release(msg)
        else:
            keyboard.release(key_map.get(msg))
    elif event_Code == 0:
        x, y = msg.split(",")
        mouse.position = (float(x), float(y))
    elif event_Code == 7:
        dx, dy = msg.split(",")
        mouse.scroll(int(dx), int(dy))
    elif event_Code in (1, 2, 3):
        mouse.press(find_button(btn_code, event_Code))
    elif event_Code in (4, 5, 6):
        mouse.release(find_button(btn_code, event_Code))


def event_recived(sock,wallpaper_path):
    mouse = Mouse_controller()
    btn_code = {(1, 4): Button.left, (2, 5): Button.right, (3, 6): Button.middle}

    keyboard = Keyboard_controller()
    key_map = dict()
    for key_enum in Key:
        key_map.setdefault(key_enum.name, key_enum)

    size_of_header = 2
    prev_msg = bytes()

    try:
        while True:
            msg = data_recive(sock, size_of_header, prev_msg, 1024)
            if msg:
                data = msg[0].decode("utf-8")
                # print(data,'inside event recieve')
                event_Code = int(data[:2])
                simulate(mouse, keyboard, btn_code, key_map, event_Code, data[2:])     
                prev_msg = msg[1]                                               
    except (ConnectionAbortedError, OSError, ConnectionResetError) as e:
        print(e.strerror)


def take_screenshot(screenshot_list, cli_width, cli_height, border_width=5, border_color=(0, 255, 0)):
    sct = mss.mss()
    sct.compression_level = 6
    mon = {"top": 0, "left": 0, "width": cli_width, "height": cli_height}
    capture = True
    while capture:
        screenshot = sct.grab(mon)
        pil_image_obj = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Add border to the image
        bordered_image = Image.new('RGB', (cli_width + 2 * border_width, cli_height + 2 * border_width), border_color)
        bordered_image.paste(pil_image_obj, (border_width, border_width))

        buffer = BytesIO()
        bordered_image.save(buffer, format='jpeg', quality=20)
        compressed_data = lz4.frame.compress(buffer.getvalue())
        screenshot_list.put(compressed_data)
        buffer.close()


def take_from_list_and_send(screenshot_list, sock):
    size_of_header = 10
    try:
        while True:
            img_jpeg_data = screenshot_list.get()
            # print("inside take_from_list_and_send function while loop")
            send_data(sock, size_of_header, img_jpeg_data)
    except (ConnectionAbortedError, ConnectionResetError, OSError):
        pass


def Desktop_bg_path():
    path_buffer = ctypes.create_unicode_buffer(512)
    success = ctypes.windll.user32.SystemParametersInfoW(115, len(path_buffer), path_buffer, 0)
    if success:
        return path_buffer.value
    else:
        return None
    
    
def screen_sending():
    global process1, process2, process3, client_socket_remote
    # remote display socket
    client_socket_remote , address = server_socket.accept()
    print(f"address in scewwn sending -- {address}")
    disable_wallpaper = data_recive(client_socket_remote, 2, bytes(), 1024)
    
    if disable_wallpaper[0].decode("utf-8") == "True":
        print("wallpaper disable")
    print(f"Your Desktop is now controlled remotely ...!")

    cli_width, cli_height = ImageGrab.grab().size
    print(f"cli_width, cli_height {cli_width, cli_height}")
    resolution_msg = bytes(str(cli_width) + "," + str(cli_height), "utf-8")
    send_data(client_socket_remote, 2, resolution_msg)
     
    screenshot_sync_queue = Queue(1)
    process1 = Process(target=take_screenshot, args=(screenshot_sync_queue, cli_width, cli_height), daemon=True)
    process1.start()

    process2 = Process(target=take_from_list_and_send, args=(screenshot_sync_queue, client_socket_remote), daemon=True)
    process2.start()

    process3 = Process(target=event_recived, args=(client_socket_remote, PATH))
    process3.start()
  

def socket_listener_create(server_ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((server_ip, 1234))
    sock.listen(1)
    return sock

    
def close_socket():
    service_socket_list = [command_client_socket, client_socket_remote, chat_client_socket]
    # service_socket_list = [command_client_socket, client_socket_remote]
    for sock in service_socket_list:
        if isinstance(sock, tuple):
            continue
        if sock:
            sock.close()
            # print('sock.close()')
    print("sockets cleaned up")    


def process_cleanup():
    process_list = [process1, process2, process3]
    for process in process_list:
        if process:
            if process.is_alive():
                process.kill()
            process.join()
    print("Remote controlled capture stopped due to process cleanup.")


def reset_ui():
    local_ip_text.configure(state="normal")
    password_text.configure(state="normal")
    password_text.delete(0, "end")
      

def start_listining(option_value):
    global client_socket_remote, server_socket, PASSWORD, login_thread, password_entered_time

         # Disable buttons
    start_btn.configure(state=tk.DISABLED)
    radio_btn.configure(state=tk.DISABLED)
    connection_frame.grid_forget()

    # Random password generation uppercase + number and length is 6
    PASSWORD = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    # PASSWORD = "123ABC"
    password_entered_time = time.time()

    if option_value == 1:
        server_ip = socket.gethostbyname(socket.gethostname())  # Local IP

        # Local IP details
        local_ip_label.grid(row=0, column=0, sticky=tk.W, pady=2)
        local_ip_text.insert(1.0, "{:<15} (Works when on same wifi or network)".format(server_ip))
        local_ip_text.configure(font=normal_font, state='disabled')
        local_ip_text.grid(row=0, column=1, sticky=tk.W, pady=2)

        # Password Details
        password_label.grid(row=3, column=0, sticky=tk.W, pady=2)
        password_text.insert(1.0, "{:<15}".format(PASSWORD))
        password_text.configure(font=normal_font, state='disabled')
        password_text.grid(row=3, column=1, sticky=tk.W, pady=2)
        stop_btn.grid(row=4, column=0, columnspan=2, sticky=tk.N, pady=(30, 2))
        # elif option_value == 2:
            # screen_sharing()

    server_socket = socket_listener_create(server_ip, 1234)
    login_thread = Thread(target=login_to_connect, args=(server_socket,), name="login_thread", daemon=True)
    login_thread.start()

    # Enable button
    details_frame.grid(row=1, column=0, padx=40, pady=40)
    stop_btn.configure(state=tk.NORMAL)

    # Start the password expiration checking thread
    expiration_thread = Thread(target=check_password_expiration, daemon=True)
    expiration_thread.start()
   

def is_password_expired():
    global password_entered_time,client_socket_remote,server_socket,PASSWORD,login_thread,IS_CLIENT_CONNECTED

    if password_entered_time is not None:
        elapsed_time = time.time() - password_entered_time
        if elapsed_time >= 30* 60:  # 30 minutes - if elapsed_time >= 30 * 60:  # 30 minutes
            print("Password Expired")
            messagebox.showinfo("Password Expired", "Your password has expired. Please login again.")
            close_socket()
            stop_listining() 
            IS_CLIENT_CONNECTED=False
            client_socket_remote = None
            server_socket = None
            PASSWORD = None
            login_thread = None
            password_entered_time = None


def check_password_expiration():
    while True:
        is_password_expired()
        time.sleep(2)
        

def stop_listining():
    global server_socket, client_socket_remote, url, file_client_socket

    if IS_CLIENT_CONNECTED:
     result = messagebox.askquestion("Disconnect", "Are you sure you want to disconnect?")
    if result == 'yes':
        send_data(command_client_socket, HEADER_COMMAND_SIZE, bytes("disconnect", "utf-8"))
    else:
        return
    
    # Closing all the sockets
    if server_socket:
        server_socket.close()
        print("I am in the server close function")
    close_socket()
    process_cleanup()

    if radio_var.get() == 1:
        local_ip_label.grid_forget()
        local_ip_text.grid_forget()
        local_ip_text.configure(state="normal")
        local_ip_text.delete('1.0', tk.END)

    label_status.configure(font=normal_font, text="Not Connected", image=red)

    connection_frame.grid(row=1, column=0, padx=120, pady=80, sticky=tk.W)  # Enable buttons
    start_btn.configure(state=tk.NORMAL)
    radio_btn.configure(state=tk.NORMAL)
    label_status.configure(font=normal_font, text="Not Connected", image=red)

    # Disable button
    stop_btn.configure(state=tk.DISABLED)
    details_frame.grid_forget()
    my_screen.hide(1)

    password_label.grid_forget()
    password_text.grid_forget()
    password_text.configure(state="normal")
    password_text.delete('1.0', tk.END)
   
    
        
def login_to_connect(sock):
    global command_client_socket, client_socket_remote, thread1, file_client_socket, IS_CLIENT_CONNECTED, f_thread, chat_client_socket
    
    accept = True
    try:
        while accept:
            print("\n")
            print("Start listening for incoming connection")
            
            label_status.configure(font=normal_font, text="Start listening", image=yellow)
            command_client_socket, address = sock.accept()

            print(f"Received login request from {address[0]}...")
            if messagebox.askquestion("Login Request", f"Received login request from {address[0]}... Do you want to connect?") == 'yes':

                received_password = data_recive(command_client_socket, 2, bytes(), 1024)[0].decode("utf-8")
                print(f'received_password : {received_password}')
                if received_password == PASSWORD:
                    send_data(command_client_socket, 2, bytes("1", "utf-8"))
                    connection_time =datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    log_message = f"Connection from {address[0]} established at {connection_time}\n"

                    # Write the log message to a file
                    with open("connection_log.txt", "a") as file:
                        file.write(log_message)

                    print("\n")
                    print(f"Connection from {address[0]} has been connected!")
                    
                    label_status.configure(font=normal_font, text="Connected", image=green)
                    thread1 = Thread(target=listinging_commands, name="listinging_commands", daemon=True)   # thread for listening command
                    thread1.start()

                    # Create a separate socket for file transfer
                    file_client_socket, file_address = sock.accept()
                    print(f'File client socket listening on {file_address[0]}')
                    # Process the file name and content as needed
                    # f_thread = Thread(target=receive_files, name='save_file',daemon=True)  # if we uncomment it, it will get overlaped and recive file name 2 times 1-correct and 
                    # f_thread.start()                                                       #  2- data and when we call it for data its printing nothing
                    
                    # chat socket
                    chat_client_socket, address = sock.accept()
                    
                    IS_CLIENT_CONNECTED = True
                    # thread for chat
                    recv_chat_msg_thread = Thread(target=receive_message, name="recv_chat_msg_thread", daemon=True)
                    recv_chat_msg_thread.start()
                    
                    my_screen.add(chat_frame, text=" Chat ")
                    
                    accept = False

                else:
                    send_data(command_client_socket, 2, bytes("0", "utf-8"))
                    print(f"{address[0]}...Please enter correct password")
                    command_client_socket.close()
                    print("command_client_socket.close()")
            else:
                command_client_socket.close()
                print("command_client_socket.close()")

    except (ConnectionAbortedError, ConnectionResetError, OSError):
        label_status.configure(font=normal_font, text="Not Connected", image=red)


def listinging_commands():
    global login_thread, IS_CLIENT_CONNECTED
    listen = True
    try:
        while listen:
            msg = data_recive(command_client_socket, HEADER_COMMAND_SIZE, bytes(), 1024)[0].decode("utf-8")
            print(f"Message received:{msg}")
            if msg == "start_capture" or msg == '        start':
                print("start screen sending msg recive")
                screen_sending()
            elif msg == "stop_capture" or msg == '        stop':
                process_cleanup()
            # Permission request
            elif msg == 'screen_sharing' or msg == '        screen':
                send_data(command_client_socket, HEADER_COMMAND_SIZE, bytes("permission_request", "utf-8"))
                permission_response = data_recive(command_client_socket, HEADER_COMMAND_SIZE, bytes(), 1024)[0].decode("utf-8")
                if permission_response == "allow_access":
                    screen_sending_client()
                else:
                    print("Permission denied. Remote display screen access not granted in listening command.")    
            # elif msg == 'screen_sharing' or msg == '        screen':
            #         permission_response = messagebox.askquestion('Permission',"Allow to share screen")
            #         if permission_response == "Yes":
            #             send_data(command_client_socket, HEADER_COMMAND_SIZE, bytes("allow_access", "utf-8"))
            #             screen_sending_client()
            #         else:
            #             send_data(command_client_socket, HEADER_COMMAND_SIZE, bytes("deny_access", "utf-8"))
            #             print("Permission denied. Remote display screen access not granted in listening command.")
            elif msg == '        start_file_' or msg == 'start_file_explorer':
                receive_files()    
            elif msg == "disconnect":
                listen = False
                print("Disconnect message received")
    except (ConnectionAbortedError, ConnectionResetError, OSError) as e:
        print(e.strerror)
    except ValueError:
        pass
    finally:
        IS_CLIENT_CONNECTED = False
        close_socket()
        process_cleanup()
        login_thread = Thread(target=login_to_connect, name="login_to_connect", args=(server_socket,), daemon=True)
        login_thread.start()
        print("Thread1 automatically closed")


def screen_sending_client():
    global process1, process2, process3, client_socket_remote
    # remote display socket
    client_socket_remote, address = server_socket.accept()
    cli_width, cli_height = ImageGrab.grab().size
    resolution_msg = bytes(str(cli_width) + "," + str(cli_height), "utf-8")

    # Send permission request to the server
    send_data(client_socket_remote, 1, bytes("permission_request", "utf-8"))

    # Receive permission response from the server
    permission_response = data_recive(client_socket_remote, 1, bytes(), 1024)[0].decode("utf-8")

    if permission_response == "allow_access":
        # Permission granted
        print("Permission granted. Starting remote display screen.")

        data = send_data(client_socket_remote, 2, resolution_msg)
        print(f"resolution_msg: {resolution_msg}")
        print(data)

        screenshot_sync_queue = Queue(1)
        process1 = Process(target=take_screenshot, args=(screenshot_sync_queue, cli_width, cli_height), daemon=True)
        process1.start()

        process2 = Process(target=take_from_list_and_send, args=(screenshot_sync_queue, client_socket_remote), daemon=True)
        process2.start()
    else:
        # Permission denied
        print("Permission denied. Remote display screen access not granted screen_sending_client.")

            
forbidden_extensions = [".exe", ".dll"]
def receive_files():
    try:
        while True:
            directory = os.path.join(os.getcwd(), 'Received')
            os.makedirs(directory, exist_ok=True)
            filename = file_client_socket.recv(1024).decode()
            print('filename---', filename)

            if not filename:
                # If no filename is received, it means all files have been received
                break

            destination = os.path.join(directory, filename)

            extension = os.path.splitext(filename)[1].lower()
            if extension in forbidden_extensions:
                result = messagebox.askquestion("Download File",
                                                f"Are you sure you want to download the file: {filename}?\nDownloading forbidden file types (.exe, .dll) can be risky.")
                if result != "yes":
                    print(f"Skipping file: {filename}")
                    continue

            with open(destination, 'wb') as file:
               while True:
                    data = file_client_socket.recv(1024)
                    if data:    
                        file.write(data)
                    break    

            print('File successfully received:', filename)

            connection_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"{filename} File successfully received from {socket.gethostbyname(socket.gethostname())} at {connection_time}\n"

            with open("connection_log.txt", "a") as file:
                file.write(log_message)

            messagebox.showinfo("File Received", f"File '{filename}' received successfully!")

    except UnicodeDecodeError:
        pass


def add_chat_display(msg,name):
    current_time = datetime.now().strftime("%H:%M")
    formatted_message = f"{msg} \n {current_time}"
    text_chat_tab.configure(state=tk.NORMAL)
    text_chat_tab.insert(tk.END, "\n")
    text_chat_tab.insert(tk.END, name + ": " + formatted_message)
    text_chat_tab.configure(state="disabled")
    

def send_message():
    try:
        msg = input_text_widget.get()
        print("send_message",msg)
        if msg and msg.strip() != "":
            input_text_widget.delete(0, "end")
            
            send_data(chat_client_socket, CHAT_HEADER_SIZE, bytes(msg, "utf-8"))
            add_chat_display(msg, LOCAL_NAME)
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError) as e:
        print(e.strerror)

        
def receive_message():
    try:
        while True:
            msg = data_recive(chat_client_socket, CHAT_HEADER_SIZE, bytes())[0].decode("utf-8")
            print("receive_message",msg)

            add_chat_display(msg, REMOTE_NAME)
            if not is_chat_window_open():
                messagebox.showinfo("New Message", "You have a new message!")
            # text_chat_tab.tag_configure("green", foreground="green")
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError) as e:
        print(e.strerror)
    except ValueError:
        pass

def is_chat_window_open():
    return chat_frame.winfo_exists() and chat_frame.winfo_viewable()


        
if __name__ == "__main__":
    
    freeze_support()
    PATH = Desktop_bg_path()
    server_socket = None
    client_socket_remote = None
    file_client_socket = None
    chat_client_socket = None
    command_client_socket = None
    
    thread1 = None
    f_thread = None
    login_thread = None
    server_ip = str()
    process1 = None
    process2 = None
    process3 = None
    password_entered_time = None
    PASSWORD = str()
    url = str()
    port = 1234
    HEADER_COMMAND_SIZE = 2
    FILE_HEADER_SIZE = 10
    CHAT_HEADER_SIZE = 10
    IS_CLIENT_CONNECTED = False
    LOCAL_NAME = "Me"
    REMOTE_NAME = "Remote"

    root = tk.Tk()
    root.title("Remote Box")
    root.resizable(False, False)

    # My Screen Notebook
    my_screen = ttk.Notebook(root)
    my_screen.grid(row=0, column=0, pady=5, columnspan=2)
    listener_frame = tk.LabelFrame(my_screen)
    listener_frame.grid(row=0, column=0)
    
    # trying to set background image to root  
    img= Image.open('./assets/background.png')
    resized_image= img.resize((700,400), Image.LANCZOS)
    new_image= ImageTk.PhotoImage(resized_image)
    label = tk.Label(listener_frame, image=new_image,background='white')
    label.place(x=0, y=0)
    
    #Images
    yellow = tk.PhotoImage(file="./assets/yellow_dot.png")
    green = tk.PhotoImage(file="./assets/green_dot.png")
    red = tk.PhotoImage(file="./assets/red_dot.png")

    label_note = tk.Label(listener_frame, anchor=tk.CENTER)
    label_note.grid(row=0, column=0, padx=200, pady=5, columnspan=2, sticky=tk.N)
    
    heading_font = Font(family="Verdana", size=17, weight="bold")
    title_font = Font(family="Verdana", size=14, weight='normal')
    title_font_normal = Font(family="Verdana", size=13, weight="bold")
    normal_font = Font(family="Verdana", size=13)

    heading = tk.Label(listener_frame, text="Remote Control Access",font=heading_font ,bg='whitesmoke',fg='brown')  
    heading.place(x=150,y=43)  

    # Connection Frame
    connection_frame = tk.LabelFrame(listener_frame, text="Connection Mode", padx=90, pady=30 ,fg='brown')
    connection_frame.configure(font=title_font,background='whitesmoke')
    connection_frame.grid(row=1, column=0, padx=120, pady=80, sticky=tk.W)
    send_window = tk.LabelFrame(my_screen,padx=100, pady=5, bd=0)
    send_window.configure(bg='#f4fdfe')
    # icon = tk.PhotoImage(file='assets/send.png')
    
    # btn = tk.Button(send_window,text='Receive',command=Ui_file).grid()

    radio_var = tk.IntVar()
    radio_var.set(1)
    radio_btn = tk.Radiobutton(connection_frame, text="IP", variable=radio_var, value=1)
    radio_btn.configure(font=normal_font,background='whitesmoke')
    radio_btn.grid(row=0, column=0, sticky=tk.W, padx=20, pady=5)
    
    start_btn = tk.Button(connection_frame, text="Start Listining", padx=2, pady=1, command=lambda: start_listining(radio_var.get()))
    start_btn.configure(font=title_font_normal,bg='red4',fg='white')
    start_btn.grid(row=2, column=0, sticky=tk.W, pady=(20, 2), padx=(20, 2))

    # Details Frame
    details_frame = tk.LabelFrame(listener_frame, text="Allow Remote Access", padx=20, pady=20, labelanchor=tk.NE ,fg='brown')
    details_frame.configure(font=title_font,background='whitesmoke')
    details_frame.grid(row=1, column=0, padx=40, pady=40)
    
   
    # Local IP Design
    local_ip_label = tk.Label(details_frame, text="LOCAL IP       :", padx=5, pady=5 )
    local_ip_label.configure(font=title_font_normal,bg='whitesmoke',fg='brown')
    local_ip_text = tk.Text(details_frame, background="white",width=47, height=1,pady=5)
    
    # Password Design
    password_label = tk.Label(details_frame, text="PASSWORD    :", padx=5, pady=5)
    password_label.configure(font=title_font_normal,bg='whitesmoke',fg='brown')
    password_text = tk.Text(details_frame, background="white",width=47, height=1,pady=5)

    stop_btn = tk.Button(details_frame, text="Stop Listining", padx=2, pady=1, command=lambda: stop_listining())
    stop_btn.configure(font=title_font_normal, state="disabled",bg='brown',fg='white')
    
    details_frame.grid_forget()
    
    label_status = tk.Label(root, text="Not Connected", image=red, compound=tk.LEFT, relief=tk.SUNKEN, anchor=tk.E, padx=10)
    label_status.configure(font=normal_font,background='whitesmoke',fg='brown')
    label_status.grid(row=3, column=0, columnspan=2, sticky=tk.W + tk.E)
    
    #chat UI==========================================
    chat_frame = tk.LabelFrame(my_screen, padx=20, pady=20, bd=0 , width=50,height=5,background="aliceblue")
    chat_frame.grid(row=1, column=0, sticky=tk.N)
    
    text_chat_tab = scrolledtext.ScrolledText(chat_frame, width=40, height=20,font=("Verdana", 12),background="aliceblue")
    text_chat_tab.grid(row=0, column=0, sticky=tk.N)
    text_chat_tab.configure(state="disabled")

    input_text_frame = tk.LabelFrame(chat_frame, pady=5, bd=0,background="aliceblue")
    input_text_frame.grid(row=1, column=0, sticky=tk.W)

    input_text_widget = tk.Entry(input_text_frame, width=40,background="mintcream" , highlightcolor="blue")
    input_text_widget.configure(font=("Verdana", 14))
    input_text_widget.bind("<Return>", send_message)
    input_text_widget.grid(row=0, column=0, pady=10, sticky=tk.W)

    send_icon = tk.PhotoImage(file="assets/img/send.png")
    send_button = tk.Button(input_text_frame, image=send_icon, command=send_message,background="aliceblue",bd=0)
    send_button.grid(row=0, column=1, pady=10,padx=10 , sticky=tk.W)
    
    # Create Tab 
    tab_style = ttk.Style()
    tab_style.configure('TNotebook.Tab', font=title_font_normal)
    
    my_screen.add(listener_frame, text=" Remote Access Connection")
    my_screen.add(chat_frame, text=" Chat ")
    # my_screen.add(send_window,text=" File ")
    
    my_screen.hide(1)
    root.mainloop()