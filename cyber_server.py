import socket
import threading
import tkinter as tk
from tkinter import Label, scrolledtext, Toplevel, Listbox
from constants import IP, PORT
from db_manager import DatabaseManager
from create_tables import create_all_tables, populate_media_menu, fix_legacy_absolute_paths
from hide_png import DataHider
from decode_png import ImageExtractor
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os
import pygame
import time
from encrypt import Encryption

class Server:
    def __init__(self):
        self.db_manager = DatabaseManager("cyber_database.db")
        create_all_tables(self.db_manager)
        populate_media_menu(self.db_manager)
        fix_legacy_absolute_paths(self.db_manager)
        
        self.encryptor = Encryption()
        self.client_keys = {}

        self.root = tk.Tk()
        self.root.withdraw()
        self.log_text = None
        self.client_listbox = None
        self.bg_image = None
        
        self.b_dir = os.path.dirname(os.path.abspath(__file__))
        self.search_var = tk.StringVar()
        self.last_file_label = None

    def play_audio(self):
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(os.path.join(self.b_dir, "sample-3s.mp3"))
            pygame.mixer.music.play()
        except Exception:
            pass

    def update_gui_log(self, message):
        self.root.after(0, lambda: self._safe_update_log(message))

    def _safe_update_log(self, message):
        if self.log_text:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.config(state=tk.DISABLED)
            self.log_text.yview(tk.END)

    def update_client_list(self):
        self.root.after(0, self._safe_update_client_list)

    def _safe_update_client_list(self):
        if not self.client_listbox:
            return
        self.client_listbox.delete(0, tk.END)
        
        clients = self.db_manager.get_all_rows("clients")
        search_query = self.search_var.get().strip().lower()

        if not clients:
            return

        for client in clients:
            client_id = client["client_id"]
            client_ip = client["ip_address"] or "N/A"
            is_online = client["is_online"]
            total_sent = client["total_sent_media"] or 0
            total_hidden = client["total_hidden_media"] or 0
            total_decoded = client["total_decoded_media"] or 0

            if search_query and search_query not in str(client_id).lower() and search_query not in str(client_ip).lower():
                continue

            status_str = "CONNECTED" if is_online == 1 else "Offline"
            display_text = f"[{status_str}] ID: {client_id[:10]}... | IP: {client_ip} | Sent: {total_sent} | Hidden Found: {total_hidden}"
            self.client_listbox.insert(tk.END, display_text)

    def handle_client(self, client_socket):
        auth_client_id = 'unknown'
        hashed_username = None
        try:
            auth_action = self.encryptor.receive_encrypted_message(client_socket)
            if not auth_action:
                return

            hashed_username = self.encryptor.receive_encrypted_message(client_socket)
            hashed_password = self.encryptor.receive_encrypted_message(client_socket)
            
            client_ip, client_port = client_socket.getpeername()
            existing_clients = self.db_manager.get_rows_with_value("clients", "client_id", hashed_username)

            if auth_action == "REGISTER":
                if existing_clients:
                    self.encryptor.send_encrypted_message(client_socket, "Username already exists.")
                    client_socket.close()
                    return
                else:
                    self.db_manager.insert_row(
                        "clients",
                        "(client_id, ip_address, port, last_login, ddos_blocked, total_sent_media, total_hidden_media, total_decoded_media, is_online, password_hash)",
                        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (hashed_username, client_ip, client_port, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, 0, 0, 0, 0, hashed_password)
                    )
                    self.encryptor.send_encrypted_message(client_socket, "REGISTRATION SUCCESS")
                    client_socket.close()
                    return
            elif auth_action == "LOGIN":
                if not existing_clients:
                    self.encryptor.send_encrypted_message(client_socket, "LOGIN_FAILED")
                    client_socket.close()
                    return
                
                client_record = existing_clients[0]
                if client_record["ddos_blocked"] == 1:
                    self.encryptor.send_encrypted_message(client_socket, "ACCOUNT_BLOCKED")
                    client_socket.close()
                    return

                stored_password = client_record["password_hash"]
                if stored_password != hashed_password:
                    fails = client_record["failed_login_attempts"] + 1
                    blocked = 1 if fails >= 5 else 0
                    self.db_manager.update_row("clients", "client_id", hashed_username, ["failed_login_attempts", "ddos_blocked"], [fails, blocked])
                    self.encryptor.send_encrypted_message(client_socket, "LOGIN_FAILED")
                    client_socket.close()
                    return

                self.db_manager.update_row("clients", "client_id", hashed_username, ["failed_login_attempts"], [0])
                self.encryptor.send_encrypted_message(client_socket, "LOGIN_SUCCESS")
                
                auth_client_id = self.encryptor.receive_encrypted_message(client_socket)
                self.encryptor.send_encrypted_message(client_socket, "CLIENT_ID_RECEIVED")
                
                personal_key = client_socket.recv(32)
                self.client_keys[auth_client_id] = personal_key

                self.db_manager.set_client_online_status(hashed_username, 1)
            else:
                client_socket.close()
                return

            self.update_gui_log("Client authenticated and connected successfully.")
            self.update_client_list()

            while True:
                self.encryptor.send_encrypted_message(client_socket, "\n1: Hide Data\n2: Decode Data\n3: Logout")
                option = self.encryptor.receive_encrypted_message(client_socket)

                if not option:
                    break

                if option == "1":
                    hider = DataHider(client_socket, self.db_manager, auth_client_id)
                    result = hider.run()
                    if result:
                        client_row = self.db_manager.get_rows_with_value("clients", "client_id", hashed_username)
                        total_sent = (client_row[0]["total_sent_media"] or 0) + 1
                        total_hid = (client_row[0]["total_hidden_media"] or 0) + 1
                        # תיקון: שימוש ב-client_id במקום id
                        self.db_manager.update_row("clients", "client_id", hashed_username, ["total_sent_media", "total_hidden_media"], [total_sent, total_hid])
                elif option == "2":
                    extractor = ImageExtractor(client_socket, self.db_manager, auth_client_id)
                    extracted_data = extractor.run()
                    if extracted_data:
                        client_row = self.db_manager.get_rows_with_value("clients", "client_id", hashed_username)
                        total_dec = (client_row[0]["total_decoded_media"] or 0) + 1
                        # תיקון: שימוש ב-client_id במקום id
                        self.db_manager.update_row("clients", "client_id", hashed_username, ["total_decoded_media"], [total_dec])
                elif option == "3":
                    self.update_gui_log("Client logged out.")
                    break
                else:
                    self.encryptor.send_encrypted_message(client_socket, "Invalid option.")
        except Exception as e:
            self.update_gui_log(f"Error handling client: {e}")
        finally:
            if hashed_username:
                self.db_manager.set_client_online_status(hashed_username, 0)
            client_socket.close()
            self.update_client_list()

    def start_server(self):
        server_socket = socket.socket()
        server_socket.bind((IP, PORT))
        server_socket.listen()
        self.update_gui_log("Server started...")
        while True:
            client_socket, _ = server_socket.accept()
            threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()

    def create_gui(self):
        self.play_audio()
        
        splash = Toplevel()
        splash.geometry("400x400")
        splash.overrideredirect(True)

        logo_path = os.path.join(self.b_dir, "idk.png")
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).resize((400, 400))
            draw = ImageDraw.Draw(logo)
            try:
                font_large = ImageFont.truetype("arial.ttf", 22)
                font_small = ImageFont.truetype("arial.ttf", 14)
            except IOError:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

            draw.text((20, 320), "MASKER - Almog Rachmani", fill="white", font=font_large)
            draw.text((320, 370), "V1.0.0", fill="white", font=font_small)

            logo_photo = ImageTk.PhotoImage(logo)
            label = Label(splash, image=logo_photo)
            label.image = logo_photo
            label.pack()

        splash.update()
        time.sleep(3)
        splash.destroy()

        self.root.destroy()
        self.root = tk.Tk()
        self.root.title("MASKER Server Management")
        self.root.geometry("550x550")

        self.log_text = scrolledtext.ScrolledText(self.root, state=tk.DISABLED, wrap=tk.WORD, height=10, bg='black', fg='white')
        self.log_text.pack(expand=True, fill='both', padx=10, pady=5)

        main_frame = tk.Frame(self.root, bg='black')
        main_frame.pack(expand=True, fill='both', padx=10, pady=5)

        header_frame = tk.Frame(main_frame, bg='black')
        header_frame.pack(fill='x', pady=5)
        
        Label(header_frame, text="Active & Historical Clients", font=("Arial", 14, "bold"), fg="white", bg="black").pack(side=tk.LEFT)
        
        search_frame = tk.Frame(header_frame, bg='black')
        search_frame.pack(side=tk.RIGHT, fill='x', expand=True, padx=(20, 0))
        Label(search_frame, text="Search:", font=("Arial", 10), fg="white", bg="black").pack(side=tk.LEFT)
        
        self.search_var.trace("w", lambda name, index, mode: self.update_client_list())
        tk.Entry(search_frame, textvariable=self.search_var, bg="#333333", fg="white", insertbackground="white").pack(side=tk.LEFT, fill='x', expand=True, padx=5)

        self.client_listbox = Listbox(main_frame, bg='black', fg='#39ff14', selectbackground="gray")
        self.client_listbox.pack(expand=True, fill='both', pady=5)
        
        self.last_file_label = Label(self.root, text="System status: Running securely", font=("Arial", 10, "italic"), fg="yellow", bg="black", anchor="w")
        self.last_file_label.pack(side=tk.BOTTOM, fill='x', padx=10, pady=5)

        threading.Thread(target=self.start_server, daemon=True).start()
        self.root.mainloop()

if __name__ == "__main__":
    server = Server()
    server.create_gui()