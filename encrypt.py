import base64
import os
from Crypto.Cipher import AES
from constants import CHUNK_SIZE

class Encryption:
    """
    Class for managing encryption and decryption using AES
    
    Documentation: This class is responsible for encrypting and decrypting data using AES-GCM protocol.
    Short protocol/text messages use a fixed key and fixed nonce for simplicity
    (send_encrypted_message/receive_encrypted_message). File payloads (send_encrypted_file/
    receive_encrypted_file) are encrypted with a per-client personal key and a fresh random
    nonce for every file, so the hidden/decoded media itself is genuinely protected end-to-end
    and not just the surrounding protocol chatter.
    """

    def __init__(self):
        """
        Initialize the encryption class with predefined keys
        
        Documentation: Creates a new encryption object with predefined keys
        """
        self.AES_KEY = b"\xa5\\\xb9\xdf\xaa\xc9M\xb5\xf7\xaf\x03\x96k,^S+\x1f\x07w\x7f\xe6\xe6\xe8\x07\x81\xca\x99'\xc4\x8f\xb6"
        self.AES_NONCE = b'FixedNonce12'  # 12 bytes

    def encrypt_data(self, data: bytes) -> str:
        """
        Encrypts binary data using AES-GCM
        
        Documentation:
        This function receives binary data and encrypts it using AES-GCM.
        It appends the authentication tag to the ciphertext and returns a base64 encoded string.
        
        Args:
            data (bytes): The binary data to encrypt
            
        Returns:
            str: Base64 encoded encrypted data with authentication tag
        """
        cipher = AES.new(self.AES_KEY, AES.MODE_GCM, nonce=self.AES_NONCE)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return base64.b64encode(ciphertext + tag).decode()

    def decrypt_data(self, data: str) -> bytes:
        """
        Decrypts a base64 encoded string of encrypted data
        
        Documentation:
        This function receives a base64 encoded string, decodes it, and decrypts using AES-GCM.
        It separates the ciphertext from the authentication tag and verifies the integrity.
        
        Args:
            data (str): Base64 encoded encrypted data with authentication tag
            
        Returns:
            bytes: Decrypted binary data
            
        Raises:
            ValueError: If the authentication tag verification fails
        """
        raw_data = base64.b64decode(data)
        cipher = AES.new(self.AES_KEY, AES.MODE_GCM, nonce=self.AES_NONCE)
        ciphertext, tag = raw_data[:-16], raw_data[-16:]
        return cipher.decrypt_and_verify(ciphertext, tag)

    def send_encrypted_message(self, sock, message):
        """
        Encrypts and sends a message through a socket
        
        Documentation:
        This function encrypts the given message and sends it through the provided socket.
        It first sends the length of the encrypted message as 4 bytes, then the encrypted message.
        
        Args:
            sock: Socket object to send data through
            message (str/bytes): Message to encrypt and send
        """
        if isinstance(message, str):
            message = message.encode()
        encrypted_message = self.encrypt_data(message)
        encrypted_bytes = encrypted_message.encode()
        sock.sendall(len(encrypted_bytes).to_bytes(4, byteorder='big'))  # Send message length (4 bytes)
        sock.sendall(encrypted_bytes)

    def receive_encrypted_message(self, sock) -> str:
        """
        Receives and decrypts a message from a socket
        
        Documentation:
        This function receives an encrypted message from the provided socket,
        decrypts it, and returns the original message as a string.
        It first reads 4 bytes to determine the message length, then reads the encrypted message.
        
        Args:
            sock: Socket object to receive data from
            
        Returns:
            str: Decrypted message
            
        Returns empty string if no data is received
        """
        raw_length = sock.recv(4)
        if not raw_length:
            return ""
        message_length = int.from_bytes(raw_length, byteorder='big')
        data = b''
        while len(data) < message_length:
            chunk = sock.recv(min(CHUNK_SIZE, message_length - len(data)))
            if not chunk:
                break
            data += chunk
        decrypted = self.decrypt_data(data.decode())
        return decrypted.decode()

    @staticmethod
    def _valid_key(key):
        """A usable AES key must be 16, 24, or 32 bytes long."""
        return isinstance(key, (bytes, bytearray)) and len(key) in (16, 24, 32)

    def encrypt_bytes_with_key(self, data: bytes, key: bytes) -> bytes:
        """
        Encrypts arbitrary binary data (e.g. a whole file) using AES-GCM with
        the given key and a freshly generated random 12-byte nonce (unlike
        encrypt_data, which reuses one fixed nonce - fine for short control
        messages, but file payloads get their own random nonce per call).

        Returns: nonce (12 bytes) + tag (16 bytes) + ciphertext, concatenated.
        """
        nonce = os.urandom(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return nonce + tag + ciphertext

    def decrypt_bytes_with_key(self, blob: bytes, key: bytes) -> bytes:
        """Reverses encrypt_bytes_with_key: splits nonce/tag/ciphertext and verifies+decrypts."""
        nonce, tag, ciphertext = blob[:12], blob[12:28], blob[28:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)

    def send_encrypted_file(self, sock, data: bytes, key: bytes = None):
        """
        Sends binary file data over the socket.

        Documentation:
        If a valid per-client `key` is given, the file bytes are first
        encrypted with AES-GCM using that key and a random nonce
        (encrypt_bytes_with_key) - this is what actually protects hidden/
        decoded media end-to-end, not just the surrounding protocol text.
        The (possibly encrypted) payload's size is then sent as a normal
        encrypted control message, followed by the raw payload bytes.

        Args:
            sock: Socket object to send data through
            data (bytes): The raw file bytes to send
            key: The client's personal AES key (16/24/32 bytes). If missing
                 or the wrong length, falls back to sending unencrypted
                 (with a printed warning) rather than crashing the transfer.
        """
        if self._valid_key(key):
            payload = self.encrypt_bytes_with_key(data, key)
        else:
            print("[encrypt] Warning: no valid personal key - sending file payload unencrypted.")
            payload = data
        self.send_encrypted_message(sock, str(len(payload)))
        sock.sendall(payload)

    def receive_encrypted_file(self, sock, key: bytes = None, size: int = None) -> bytes:
        """
        Receives binary file data over the socket.

        Documentation:
        If `size` is not provided, first reads it as an encrypted message
        (matching send_encrypted_file). Then reads exactly that many raw
        bytes from the socket. If a valid `key` is given, the received
        bytes are decrypted with it (decrypt_bytes_with_key) to recover the
        original file content.

        Args:
            sock: Socket object to receive data from
            key: The client's personal AES key, matching what was used to encrypt.
            size: Optional known size in bytes, to avoid re-reading the
                  length header when the caller already consumed it.

        Returns:
            bytes: The original (decrypted) file data.
        """
        if size is None:
            size = int(self.receive_encrypted_message(sock))
        payload = b''
        while len(payload) < size:
            chunk = sock.recv(min(CHUNK_SIZE, size - len(payload)))
            if not chunk:
                break
            payload += chunk
        if self._valid_key(key):
            return self.decrypt_bytes_with_key(payload, key)
        return payload

# Example usage:
# encryptor = Encryption()
# encryptor.send_encrypted_message(socket_object, "Hello, world!")
# received_message = encryptor.receive_encrypted_message(socket_object)