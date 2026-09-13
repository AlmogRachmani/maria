import os
from constants import MEDIA_DIR


def create_all_tables(db_manager):
    """Create all necessary tables for the application."""

    db_manager.create_table(
        "clients",
        """(
            client_id VARCHAR(255) PRIMARY KEY,   -- sha256(username), see README for why
            password_hash VARCHAR(255),
            ip_address VARCHAR(255),
            port INT,
            last_login DATETIME,
            is_online BOOLEAN DEFAULT 0,
            failed_login_attempts INT DEFAULT 0,
            ddos_blocked BOOLEAN DEFAULT 0,
            total_sent_media INT DEFAULT 0,
            total_hidden_media INT DEFAULT 0,
            total_decoded_media INT DEFAULT 0
        )"""
    )

    db_manager.create_table(
        "decrypted_media",
        """(
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(255),
            media_type_id INT,
            path_to_decrypted_media VARCHAR(255),
            has_hidden_data BOOLEAN DEFAULT 0,
            created_at DATETIME
        )"""
    )

    db_manager.create_table(
        "media_menu",
        "(id_media INTEGER PRIMARY KEY, image_path VARCHAR(255), audio_path VARCHAR(255), video_path VARCHAR(255))"
    )

    # דרישת המשתמש: להציג בממשק את שם המשתמש עצמו, לא רק את ה-hash שלו.
    # השרת מקבל רק hash של השם (למפתח ראשי/אבטחה), אז מוסיפים עמודה נפרדת
    # שתאחסן את השם הרגיל שהקליינט שולח בנוסף, לצורך תצוגה בלבד.
    db_manager.add_column_if_missing("clients", "username", "VARCHAR(255)")


def populate_media_menu(db_manager):
    """Populate media_menu with cover files that ship inside /media.

    Only the *filename* is stored -- never an absolute path -- so the
    project keeps working after being copied to any other computer.
    cyber_server.py joins these filenames with constants.MEDIA_DIR at
    runtime to get the real path on whatever machine it's running on.
    """
    predefined_media = [
        (1, "poke.jpg", None, None),
        (2, "idk.png", None, None),
        (3, "logo_cyber.jpeg", None, None),
    ]

    existing_rows = db_manager.get_all_rows("media_menu")
    if not existing_rows:
        for media in predefined_media:
            db_manager.insert_row(
                "media_menu",
                "(id_media, image_path, audio_path, video_path)",
                "(%s, %s, %s, %s)",
                media
            )


def fix_legacy_absolute_paths(db_manager):
    """Migration helper: the original DB shipped with rows that stored a
    developer's absolute Windows path (e.g. C:\\Users\\Mamriot_User\\...).
    Those rows would break on any other computer. This walks media_menu and
    decrypted_media and rewrites any absolute path down to just its
    filename, matching the convention used from now on. Safe to run every
    startup -- it's a no-op once paths are already clean."""
    for row in db_manager.get_all_rows("media_menu"):
        for col in ("image_path", "audio_path", "video_path"):
            value = row[col]
            if value and (":\\" in value or value.startswith("/") and "media" not in value):
                fixed = os.path.basename(value.replace("\\", "/"))
                db_manager.update_row("media_menu", "id_media", row["id_media"], [col], [fixed])

    for row in db_manager.get_all_rows("decrypted_media"):
        value = row["path_to_decrypted_media"]
        if value and (":\\" in value):
            fixed = os.path.basename(value.replace("\\", "/"))
            db_manager.update_row("decrypted_media", "id", row["id"], ["path_to_decrypted_media"], [fixed])