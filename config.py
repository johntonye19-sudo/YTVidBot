from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")

MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", 50))

# S3 configuration (optional)
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
