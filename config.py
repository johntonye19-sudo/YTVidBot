from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")

MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", 50))

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
