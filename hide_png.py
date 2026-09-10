from datetime import datetime
from encrypt import Encryption

class DataHider:
    """
    A class to handle the process of receiving data from a client and hiding it in a base media file.
    """

    def __init__(self, client_socket, db_manager, user_id):
        """
        Initializes the DataHider with necessary resources.
        
        """
        self.client_socket = client_socket
        self.db_manager = db_manager
        self.user_id = user_id
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

        menu_str = "\n".join([f"{item[0]}: {item[1] or item[2] or item[3]}" for item in media_menu])
        self.encryptor.send_encrypted_message(self.client_socket, menu_str)

        selected_id = self.encryptor.receive_encrypted_message(self.client_socket)
        return next(item for item in media_menu if str(item[0]) == selected_id)

    def receive_data_to_hide(self):
        """
        Receives the size and the actual binary data from the client.

        :return: The binary data sent by the client.
        """
        size = int(self.encryptor.receive_encrypted_message(self.client_socket))
        data = b''
        while len(data) < size:
            chunk = self.client_socket.recv(4096)
            if not chunk:
                break
            data += chunk
        return data

    def create_hidden_file(self, media_path, data_to_hide):
        """
        Combines the base media with the hidden data and saves it to a new file.

        :param media_path: The path to the base media file.
        :param data_to_hide: The binary data to hide.
        :return: The path to the output file.
        """
        output_path = f"hidden_{self.user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"

        with open(media_path, "rb") as media_file:
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

        media_path = selected_media[1]  # Assuming image_path
        output_path = self.create_hidden_file(media_path, data_to_hide)

        self.db_manager.insert_decrypted_media(self.user_id, 1, output_path)

        self.encryptor.send_encrypted_message(self.client_socket, f"Data successfully hidden in {output_path}")
        return selected_media[0], 1, output_path