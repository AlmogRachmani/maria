import os

CHUNK_SIZE = 4096
IP = "127.0.0.1"
PORT = 9921


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MEDIA_DIR = os.path.join(BASE_DIR, "media")     
OUTPUT_DIR = os.path.join(BASE_DIR, "output")    
DB_FILE = os.path.join(BASE_DIR, "cyber_database.db")

os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

MAX_FAILED_LOGIN_ATTEMPTS = 5
CONNECTION_RATE_LIMIT = 10      
CONNECTION_RATE_WINDOW = 10     