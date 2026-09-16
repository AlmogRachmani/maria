import socket
import os
import glob
import random
from PIL import Image
from constants import IP, PORT
from encrypt import Encryption
import hashlib

class Client:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        existing_hidden_files = glob.glob(os.path.join(self.base_dir, "hidden_*.jpg"))
        if existing_hidden_files:
            self.decrypted_list_paths = existing_hidden_files
        else:
            self.decrypted_list_paths = [
                os.path.join(self.base_dir, "mail_photo.jpg")
            ]
        self.usual_images = [
            os.path.join(self.base_dir, "IMG_3495.jpg"),
            os.path.join(self.base_dir, "REST1.png"),
            os.path.join(self.base_dir, "mitzperamon3.jpg")
        ]
        self.client_socket = None
        self.encryptor = Encryption()

        key_path = os.path.join(self.base_dir, "personal.key")
        if os.path.exists(key_path):
            with open(key_path, "rb") as file:
                self.personal_key = file.read()
        else:
            self.personal_key = os.urandom(32)
            with open(key_path, "wb") as file:
                file.write(self.personal_key)

    def connect_to_server(self):
        try:
            if self.client_socket:
                try:
                    self.client_socket.close()
                except Exception:
                    pass
            self.client_socket = socket.socket()
            self.client_socket.connect((IP, PORT))
            print("Connected to server")
        except Exception as e:
            print(f"Error connecting to server: {e}")
            self.client_socket = None

    def send_client_id(self, client_id):
        client_id = str(client_id)
        print("The client id ", client_id)
        
        self.encryptor.send_encrypted_message(self.client_socket, client_id)
        server_response = self.encryptor.receive_encrypted_message(self.client_socket)
        
        self.encryptor.send_encrypted_message(self.client_socket, self.personal_key.hex())

        print("Personal key sent to server.")
        print(server_response)
        return server_response

    def receive_menu(self):
        try:
            menu = self.encryptor.receive_encrypted_message(self.client_socket)
            print("\nOptions from server:\n")
            print(menu)
            return menu
        except Exception as e:
            print(f"Error receiving menu: {e}")
            return None

    def handle_hide_option(self):
        print("\nYou chose to hide data.")
        media_menu = self.encryptor.receive_encrypted_message(self.client_socket)
        if "No media options available." in media_menu:
            print("No media options available to hide data. Returning to menu.")
            return

        print("\nAvailable media to hide data in:\n")
        print(media_menu)

        available_ids = [line.split(":")[0].strip() for line in media_menu.splitlines() if ":" in line]
        selected_media_id = random.choice(available_ids) if available_ids else "1"
        self.encryptor.send_encrypted_message(self.client_socket, selected_media_id)

        data_to_hide_path = random.choice(self.usual_images)
        print("Data to hide:", data_to_hide_path)

        if os.path.exists(data_to_hide_path):
            with open(data_to_hide_path, "rb") as file:
                data_to_hide = file.read()
        else:
            print("File to hide does not exist. Sending empty data to stay in sync with server.")
            data_to_hide = b""

        self.encryptor.send_encrypted_file(
            self.client_socket,
            data_to_hide,
            self.personal_key
        )

        response = self.encryptor.receive_encrypted_message(self.client_socket)
        print(response)

        hidden_media_path = response.split("in ")[-1].strip()
        if os.path.exists(hidden_media_path):
            try:
                img = Image.open(hidden_media_path)
                img.show()
            except Exception as e:
                print(f"Error opening the hidden media: {e}")

    def handle_decode_option(self):
        print("\nYou chose to decode data.")
        media_path = random.choice(self.decrypted_list_paths)
        print("Decrypted file chosen:", media_path)

        if os.path.exists(media_path):
            with open(media_path, "rb") as file:
                data = file.read()
        else:
            print("File does not exist. Sending empty data to stay in sync with server.")
            data = b""

        self.encryptor.send_encrypted_file(
            self.client_socket,
            data,
            self.personal_key
        )

        num_images = int(self.encryptor.receive_encrypted_message(self.client_socket))
        print(f"Found {num_images} hidden images.")

        for i in range(num_images):
            image_data = self.encryptor.receive_encrypted_file(
                self.client_socket,
                self.personal_key
            )

            decoded_file_path = f"decoded_image_{i + 1}.jpg"
            with open(decoded_file_path, "wb") as file:
                file.write(image_data)

            print(f"Decoded image saved at {decoded_file_path}")
            if os.path.exists(decoded_file_path):
                try:
                    img = Image.open(decoded_file_path)
                    img.show()
                except Exception as e:
                    print(f"Error opening the decoded image: {e}")

    def register(self):
        if not self.client_socket:
            self.connect_to_server()

        username = input("Enter username for registration: ")
        password = input("Enter password for registration: ")
        hashed_username = self.hash_value(username)
        hashed_password = self.hash_value(password, salt=hashed_username)

        try:
            self.encryptor.send_encrypted_message(self.client_socket, "REGISTER")
            self.encryptor.send_encrypted_message(self.client_socket, hashed_username)
            self.encryptor.send_encrypted_message(self.client_socket, hashed_password)
            self.encryptor.send_encrypted_message(self.client_socket, username)

            response = self.encryptor.receive_encrypted_message(self.client_socket)
            print(response)
            return response
        except Exception as e:
            print(f"Connection error during registration: {e}")
            return None

    def login(self):
        if not self.client_socket:
            self.connect_to_server()

        username = input("Enter username: ")
        password = input("Enter password: ")
        hashed_username = self.hash_value(username)
        hashed_password = self.hash_value(password, salt=hashed_username)

        try:
            self.encryptor.send_encrypted_message(self.client_socket, "LOGIN")
            self.encryptor.send_encrypted_message(self.client_socket, hashed_username)
            self.encryptor.send_encrypted_message(self.client_socket, hashed_password)
            self.encryptor.send_encrypted_message(self.client_socket, username)

            response = self.encryptor.receive_encrypted_message(self.client_socket)
            print(response)
            return response
        except Exception as e:
            print(f"Connection error during login: {e}")
            return None

    def hash_value(self, value, salt=""):

        return hashlib.sha256((value + salt).encode()).hexdigest()

    def run(self):
        while True:
            self.connect_to_server()
            if not self.client_socket:
                return

            print("\n===== MASKER =====")
            print("1. Register")
            print("2. Login")
            print("3. Exit")

            choice = input("Choose an option: ")

            if choice == "1":
                self.register()
                if self.client_socket:
                    self.client_socket.close()
            elif choice == "2":
                response = self.login()
                if response == "LOGIN_SUCCESS":
                    client_id = str(random.randint(1, 6))
                    self.send_client_id(client_id)
                    break
                else:
                    print("Login failed. Please register first or try again.")
                    if self.client_socket:
                        self.client_socket.close()
            elif choice == "3":
                if self.client_socket:
                    self.client_socket.close()
                return
            else:
                print("Invalid choice.")
                if self.client_socket:
                    self.client_socket.close()

        while True:
            menu = self.receive_menu()
            if not menu:
                break
            if menu.startswith("SERVER_ERROR"):
                print("Server reported an error and closed this connection.")
                break

            option = input("Choose an option (1-3): ").strip()
            print("Chosen option:", option)
            self.encryptor.send_encrypted_message(self.client_socket, option)

            if option == "1":
                self.handle_hide_option()
            elif option == "2":
                self.handle_decode_option()
            elif option == "3":
                print("Logging out...")
                break
            else:
                print("Invalid option chosen.")

        if self.client_socket:
            self.client_socket.close()

if __name__ == "__main__":
    client = Client()
    client.run()



    def play_audio(self):
    
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(os.path.join(self.b_dir, "background_theme.mp3"))
                pygame.mixer.music.play()
                pygame.mixer.music.queue("LedZeppelin-_Stairway_To_Heaven_HQ_320kb(mp3.pm).mp3")
    
                def start_background_loop():
                    try:
                        pygame.mixer.music.load(os.path.join(self.b_dir, "background_theme.mp3"))
                        pygame.mixer.music.play(loops=-1)
                    except Exception:
                        pass
    
                threading.Timer(2.6, start_background_loop).start()
            except Exception:
                pass