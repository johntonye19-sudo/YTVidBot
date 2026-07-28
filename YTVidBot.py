import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Limit for standard Telegram bots to upload files is 50MB
TELEGRAM_FILE_LIMIT_MB = 50 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    await update.message.reply_text(
        "Hi! Send me a YouTube link, and I will help you download the video or extract the audio."
    )

def extract_video_info(url: str) -> dict:
    """Helper to extract video info using yt-dlp in a synchronous context."""
    ydl_opts = {}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title', 'video'),
            'duration': info.get('duration', 0),
            'id': info.get('id'),
        }

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes incoming messages, checks for links, and displays download choices."""
    url = update.message.text.strip()
    
    if not ("youtube.com" in url or "youtu.be" in url):
        await update.message.reply_text("Please send a valid YouTube link.")
        return

    status_message = await update.message.reply_text("Processing link... Please wait.")
    
    try:
        # Run synchronous metadata extraction in a separate thread to prevent blocking the event loop
        info = await asyncio.to_thread(extract_video_info, url)
        
        # Save URL and metadata in user_data for retrieval during callback handling
        context.user_data['url'] = url
        context.user_data['title'] = info['title']
        
        keyboard = [
            [
                InlineKeyboardButton("Download Video (MP4)", callback_data='dl_video'),
                InlineKeyboardButton("Download Audio (MP3)", callback_data='dl_audio')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await status_message.edit_text(
            f"Title: {info['title']}\nChoose your preferred format below:",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error extracting metadata: {e}")
        await status_message.edit_text("Failed to extract video information. The link might be broken or private.")

def download_sync(url: str, download_type: str) -> str:
    """Synchronous download task using yt-dlp."""
    output_template = os.path.join(DOWNLOAD_DIR, '%(title)s_%(id)s.%(ext)s')
    
    if download_type == 'video':
        ydl_opts = {
            # Selects best mp4 format under 50MB (often 720p or 360p)
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_template,
            'max_filesize': TELEGRAM_FILE_LIMIT_MB * 1024 * 1024,
        }
    else:  # audio
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        
        if download_type == 'audio':
            # After conversion, the extension changes to mp3
            filename = os.path.splitext(filename)[0] + ".mp3"
            
        return filename

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the user's choice (Video or Audio)."""
    query = update.call

