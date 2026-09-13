from datetime import datetime
from encrypt import Encryption
from constants import MEDIA_DIR
import os

class DataHider:
    """
    A class to handle the process of receiving data from a client and hiding it in a base media file.
    """

    def __init__(self, client_socket, db_manager, user_id, personal_key=None):
        """
        Initializes the DataHider with necessary resources.

        Args:
            personal_key: The connected client's unique AES key (received
                          during login) - used to actually decrypt the file
                          payload the client sends, instead of just passing
                          the raw bytes through.
        """
        self.client_socket = client_socket
        self.db_manager = db_manager
        self.user_id = user_id
        self.personal_key = personal_key
        self.encryptor = Encryption()

    def fetch_media_menu(self):
        """
        Retrieves the media menu from the database and sends it to the client.

        :return: The selected media item as a row (tuple), or None if there's no available media.
        """
        media_menu = self.db_manager.get_all_rows("media_menu")
        if not media_menu:
            self.encryptor.send_encrypted_message(self.client_socket, "No media options available.")
            return None

        menu_str = "\n".join(
            [f"{item['id_media']}: {item['image_path'] or item['audio_path'] or item['video_path']}" for item in media_menu]
        )
        self.encryptor.send_encrypted_message(self.client_socket, menu_str)

        selected_id = self.encryptor.receive_encrypted_message(self.client_socket)
        return next(item for item in media_menu if str(item['id_media']) == selected_id)

    def receive_data_to_hide(self):
        """
        Receives the encrypted file payload from the client and decrypts it
        with the client's personal key, returning the original binary data.

        :return: The (decrypted) binary data sent by the client.
        """
        return self.encryptor.receive_encrypted_file(self.client_socket, self.personal_key)

    def create_hidden_file(self, media_path, data_to_hide):
        """
        Combines the base media with the hidden data and saves it to a new file.

        :param media_path: The path to the base media file.
        :param data_to_hide: The binary data to hide.
        :return: The path to the output file.
        """
        output_path = f"hidden_{self.user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"

        # media_path כפי שמגיע מ-media_menu הוא רק שם קובץ (למשל "poke.jpg").
        # הוא יכול להימצא בתוך MEDIA_DIR (הקונבנציה המתוכננת) או ישירות בתיקיית
        # השורש של הפרויקט (איך שהקבצים בפועל יושבים אצל חלק מהמשתמשים) -
        # בודקים את שניהם כדי לא להיכשל בגלל מיקום שונה בין מחשבים.
        candidate_paths = [
            os.path.join(MEDIA_DIR, media_path),
            media_path,
        ]
        full_media_path = next((p for p in candidate_paths if os.path.exists(p)), None)
        if full_media_path is None:
            raise FileNotFoundError(
                f"Could not find media file '{media_path}' in MEDIA_DIR or project root."
            )

        with open(full_media_path, "rb") as media_file:
            media_data = media_file.read()

        with open(output_path, "wb") as output_file:
            output_file.write(media_data + data_to_hide)

        return output_path

    def run(self):
        """
        The main method that orchestrates the hiding process.

        :return: Tuple with (media_id, media_type_id, output_path)
        """
        selected_media = self.fetch_media_menu()
        if not selected_media:
            return

        data_to_hide = self.receive_data_to_hide()

        media_path = selected_media['image_path']  # column name, not positional index
        output_path = self.create_hidden_file(media_path, data_to_hide)

        self.db_manager.insert_decrypted_media(self.user_id, 1, output_path)

        self.encryptor.send_encrypted_message(self.client_socket, f"Data successfully hidden in {output_path}")
        return selected_media['id_media'], 1, output_path