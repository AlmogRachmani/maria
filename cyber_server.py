import socket
import threading
import tkinter as tk
from tkinter import ttk, Label, scrolledtext, Toplevel
from constants import IP, PORT
from db_manager import DatabaseManager
from create_tables import create_all_tables, populate_media_menu, fix_legacy_absolute_paths
from hide_png import DataHider
from decode_png import ImageExtractor
from datetime import datetime
from PIL import Image, ImageTk
import os
import pygame
import time
from encrypt import Encryption

BG_DARK = "#160707"
BG_PANEL = "#1f0a0a"
BG_FIELD = "#2a0e0e"
GOLD = "#e8b923"
GOLD_LIGHT = "#ffe9a8"
CREAM = "#f5e6c8"
CONNECTED_GREEN = "#39ff14"
OFFLINE_GRAY = "#8a7f6a"
TITLE_FONT = ("Georgia", 22, "bold")
SUBTITLE_FONT = ("Georgia", 10, "italic")
SECTION_FONT = ("Georgia", 13, "bold")
BODY_FONT = ("Georgia", 10)


class Server:
    def __init__(self):
        self.db_manager = DatabaseManager("localhost", "root", "almog151", "cyber_database")
        create_all_tables(self.db_manager)
        populate_media_menu(self.db_manager)
        fix_legacy_absolute_paths(self.db_manager)

        self.encryptor = Encryption()
        self.client_keys = {}

        self.root = tk.Tk()
        self.root.withdraw()
        self.log_text = None
        self.connected_tree = None
        self.history_tree = None
        self._icon_photo = None  

        self.b_dir = os.path.dirname(os.path.abspath(__file__))
        self.assets_dir = self.b_dir  
        self.search_var = tk.StringVar()
        self.last_file_label = None

    def _asset(self, filename):
        return os.path.join(self.assets_dir, filename)

    def play_audio(self):
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(os.path.join(self.b_dir, "background_theme.mp3"))
            pygame.mixer.music.play()
            pygame.mixer.music.queue("Led_Zeppelin_-_Stairway_To_Heaven_HQ_320_kb_(mp3.pm).mp3")



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

    def _display_name(self, client):
        return client["username"] if "username" in client.keys() and client["username"] else f"{client['client_id'][:10]}..."

    def _safe_update_client_list(self):
        if not self.connected_tree or not self.history_tree:
            return

        for row in self.connected_tree.get_children():
            self.connected_tree.delete(row)
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)

        clients = self.db_manager.get_all_rows("clients")
        search_query = self.search_var.get().strip().lower()

        if not clients:
            return

        for client in clients:
            client_id = client["client_id"]
            client_ip = client["ip_address"] or "N/A"
            client_username = client["username"] if "username" in client.keys() and client["username"] else ""

            if search_query and (
                search_query not in str(client_id).lower()
                and search_query not in str(client_ip).lower()
                and search_query not in str(client_username).lower()
            ):
                continue

            display_name = self._display_name(client)
            is_online = client["is_online"] == 1
            status_text = "● CONNECTED" if is_online else "○ Offline"
            tag = "online" if is_online else "offline"
            sent = client["total_sent_media"] or 0
            hidden = client["total_hidden_media"] or 0
            decoded = client["total_decoded_media"] or 0

            row_values = (status_text, display_name, sent, hidden, decoded)
            self.history_tree.insert("", tk.END, values=row_values, tags=(tag,))
            if is_online:
                self.connected_tree.insert("", tk.END, values=row_values, tags=(tag,))

    def handle_client(self, client_socket):
        auth_client_id = 'unknown'
        hashed_username = None
        try:
            auth_action = self.encryptor.receive_encrypted_message(client_socket)
            if not auth_action:
                return

            hashed_username = self.encryptor.receive_encrypted_message(client_socket)
            hashed_password = self.encryptor.receive_encrypted_message(client_socket)
            plain_username = self.encryptor.receive_encrypted_message(client_socket)

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
                        "(client_id, ip_address, port, last_login, ddos_blocked, total_sent_media, total_hidden_media, total_decoded_media, is_online, password_hash, username)",
                        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (hashed_username, client_ip, client_port, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, 0, 0, 0, 0, hashed_password, plain_username)
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

                self.db_manager.update_row("clients", "client_id", hashed_username, ["failed_login_attempts", "username"], [0, plain_username])
                self.encryptor.send_encrypted_message(client_socket, "LOGIN_SUCCESS")

                auth_client_id = self.encryptor.receive_encrypted_message(client_socket)
                self.encryptor.send_encrypted_message(client_socket, "CLIENT_ID_RECEIVED")

                personal_key_hex = self.encryptor.receive_encrypted_message(client_socket)
                try:
                    personal_key = bytes.fromhex(personal_key_hex)
                except (ValueError, TypeError):
                    personal_key = b""
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
                    hider = DataHider(client_socket, self.db_manager, auth_client_id, self.client_keys.get(auth_client_id))
                    result = hider.run()
                    if result:
                        client_row = self.db_manager.get_rows_with_value("clients", "client_id", hashed_username)
                        total_sent = (client_row[0]["total_sent_media"] or 0) + 1
                        total_hid = (client_row[0]["total_hidden_media"] or 0) + 1
                        self.db_manager.update_row("clients", "client_id", hashed_username, ["total_sent_media", "total_hidden_media"], [total_sent, total_hid])
                        self.update_client_list()
                elif option == "2":
                    extractor = ImageExtractor(client_socket, self.db_manager, auth_client_id, self.client_keys.get(auth_client_id))
                    extracted_data = extractor.run()
                    if extracted_data:
                        client_row = self.db_manager.get_rows_with_value("clients", "client_id", hashed_username)
                        total_dec = (client_row[0]["total_decoded_media"] or 0) + 1
                        self.db_manager.update_row("clients", "client_id", hashed_username, ["total_decoded_media"], [total_dec])
                        self.update_client_list()
                elif option == "3":
                    self.update_gui_log("Client logged out.")
                    break
                else:
                    self.encryptor.send_encrypted_message(client_socket, "Invalid option.")
        except Exception as e:
            self.update_gui_log(f"Error handling client: {e}")
            try:
                self.encryptor.send_encrypted_message(client_socket, f"SERVER_ERROR: {e}")
            except Exception:
                pass 
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

    # GUI

    def _show_splash(self):
        splash = Toplevel()
        splash.overrideredirect(True)
        splash.configure(bg=BG_DARK)

        splash_path = self._asset("splash.png")
        if os.path.exists(splash_path):
            img = Image.open(splash_path)
            w, h = img.size
            photo = ImageTk.PhotoImage(img)
            screen_w = splash.winfo_screenwidth()
            screen_h = splash.winfo_screenheight()
            x = (screen_w - w) // 2
            y = (screen_h - h) // 2
            splash.geometry(f"{w}x{h}+{x}+{y}")
            label = Label(splash, image=photo, bd=0)
            label.image = photo
            label.pack()
        else:
            splash.geometry("500x300")
            Label(splash, text="MASKER", font=TITLE_FONT, fg=GOLD, bg=BG_DARK).pack(expand=True)

        splash.update()
        time.sleep(2.6)
        splash.destroy()

    def _configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(
            "Dragon.Treeview",
            background=BG_FIELD,
            fieldbackground=BG_FIELD,
            foreground=CREAM,
            rowheight=26,
            borderwidth=0,
            font=BODY_FONT,
        )
        style.configure(
            "Dragon.Treeview.Heading",
            background=BG_PANEL,
            foreground=GOLD,
            font=("Georgia", 10, "bold"),
            borderwidth=1,
        )
        style.map(
            "Dragon.Treeview",
            background=[("selected", "#4a1a0a")],
            foreground=[("selected", GOLD_LIGHT)],
        )
        style.configure("Dragon.Vertical.TScrollbar", background=BG_PANEL, troughcolor=BG_DARK, arrowcolor=GOLD)

    def _make_tree(self, parent, height):
        tree = ttk.Treeview(
            parent,
            columns=("status", "username", "sent", "hidden", "decoded"),
            show="headings",
            style="Dragon.Treeview",
            height=height,
        )
        tree.heading("status", text="Status")
        tree.heading("username", text="Username")
        tree.heading("sent", text="Sent")
        tree.heading("hidden", text="Hidden")
        tree.heading("decoded", text="Decoded")
        tree.column("status", width=120, anchor="w")
        tree.column("username", width=180, anchor="w")
        tree.column("sent", width=60, anchor="center")
        tree.column("hidden", width=60, anchor="center")
        tree.column("decoded", width=70, anchor="center")
        tree.tag_configure("online", foreground=CONNECTED_GREEN)
        tree.tag_configure("offline", foreground=OFFLINE_GRAY)
        return tree

    def _center_window(self, win, width, height):
        """Centers a Tk window on the user's screen, regardless of screen size."""
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")

    def create_gui(self):
        self.play_audio()
        self._show_splash()

        self.root.destroy()
        self.root = tk.Tk()
        self.root.title("MASKER - Dragon Steganography Server")
        self._center_window(self.root, 700, 760)
        self.root.configure(bg=BG_DARK)
        self.root.minsize(560, 600)

        icon_ico = self._asset("dragon_icon.ico")
        icon_png = self._asset("dragon_icon_64.png")
        try:
            if os.path.exists(icon_ico):
                self.root.iconbitmap(icon_ico)
        except Exception:
            pass

        self._configure_style()

        header = tk.Frame(self.root, bg=BG_PANEL, highlightbackground=GOLD, highlightthickness=1)
        header.pack(fill="x", padx=10, pady=(10, 6))

        if os.path.exists(icon_png):
            icon_img = Image.open(icon_png)
            self._icon_photo = ImageTk.PhotoImage(icon_img)
            Label(header, image=self._icon_photo, bg=BG_PANEL).pack(side=tk.LEFT, padx=10, pady=8)

        title_box = tk.Frame(header, bg=BG_PANEL)
        title_box.pack(side=tk.LEFT, pady=8)
        Label(title_box, text="MASKER", font=TITLE_FONT, fg=GOLD, bg=BG_PANEL).pack(anchor="w")

        Label(self.root, text="Server Log", font=SECTION_FONT, fg=GOLD, bg=BG_DARK).pack(anchor="w", padx=14, pady=(4, 0))
        self.log_text = scrolledtext.ScrolledText(
            self.root, state=tk.DISABLED, wrap=tk.WORD, height=7,
            bg=BG_FIELD, fg=CREAM, insertbackground=CREAM,
            highlightbackground=GOLD, highlightthickness=1, font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", padx=12, pady=(2, 8))

        main_frame = tk.Frame(self.root, bg=BG_DARK)
        main_frame.pack(expand=True, fill="both", padx=12, pady=(0, 6))

        search_frame = tk.Frame(main_frame, bg=BG_DARK)
        search_frame.pack(fill="x", pady=(0, 8))
        Label(search_frame, text="Search:", font=BODY_FONT, fg=GOLD, bg=BG_DARK).pack(side=tk.LEFT)
        self.search_var.trace("w", lambda name, index, mode: self.update_client_list())
        tk.Entry(
            search_frame, textvariable=self.search_var, bg=BG_FIELD, fg=CREAM,
            insertbackground=CREAM, relief="flat", highlightbackground=GOLD,
            highlightthickness=1, font=BODY_FONT,
        ).pack(side=tk.LEFT, fill="x", expand=True, padx=8, ipady=3)

        Label(main_frame, text="Connected Now", font=SECTION_FONT, fg=CONNECTED_GREEN, bg=BG_DARK).pack(anchor="w")
        connected_frame = tk.Frame(main_frame, bg=BG_DARK)
        connected_frame.pack(fill="both", expand=True, pady=(2, 12))
        self.connected_tree = self._make_tree(connected_frame, height=5)
        conn_scroll = ttk.Scrollbar(connected_frame, orient="vertical", command=self.connected_tree.yview, style="Dragon.Vertical.TScrollbar")
        self.connected_tree.configure(yscrollcommand=conn_scroll.set)
        self.connected_tree.pack(side=tk.LEFT, fill="both", expand=True)
        conn_scroll.pack(side=tk.RIGHT, fill="y")

        Label(main_frame, text="All Clients / History", font=SECTION_FONT, fg=GOLD, bg=BG_DARK).pack(anchor="w")
        history_frame = tk.Frame(main_frame, bg=BG_DARK)
        history_frame.pack(fill="both", expand=True, pady=(2, 4))
        self.history_tree = self._make_tree(history_frame, height=10)
        hist_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_tree.yview, style="Dragon.Vertical.TScrollbar")
        self.history_tree.configure(yscrollcommand=hist_scroll.set)
        self.history_tree.pack(side=tk.LEFT, fill="both", expand=True)
        hist_scroll.pack(side=tk.RIGHT, fill="y")

        self.last_file_label = Label(
            self.root, text="System status: Running securely 🐉", font=("Georgia", 10, "italic"),
            fg=GOLD, bg=BG_PANEL, anchor="w",
        )
        self.last_file_label.pack(side=tk.BOTTOM, fill="x")

        threading.Thread(target=self.start_server, daemon=True).start()
        self.root.mainloop()


if __name__ == "__main__":
    server = Server()
    server.create_gui()