import os
import logging
import asyncio
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from services import yt_service, storage
import config

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

DOWNLOAD_DIR = config.DOWNLOAD_DIR
MAX_FILE_MB = config.MAX_FILE_MB


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! Send me a YouTube link, and I'll help you download the video or extract the audio."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not ("youtube.com" in text or "youtu.be" in text):
        await update.message.reply_text("Please send a valid YouTube link.")
        return

    status_message = await update.message.reply_text("Processing link... Please wait.")

    try:
        info = await asyncio.to_thread(yt_service.extract_video_info, text)
        # store url and info
        context.user_data['url'] = text
        context.user_data['info'] = info

        keyboard = [
            [
                InlineKeyboardButton("Download Video (Low)", callback_data='dl_video_low'),
                InlineKeyboardButton("Download Video (High)", callback_data='dl_video_high'),
            ],
            [InlineKeyboardButton("Download Audio (MP3)", callback_data='dl_audio')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await status_message.edit_text(
            f"Title: {info.get('title')}\nChoose a format:", reply_markup=reply_markup
        )

    except Exception as e:
        logger.exception("Failed to extract metadata")
        await status_message.edit_text("Failed to extract video information. The link might be broken or private.")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    data = query.data
    user_data = context.user_data
    url = user_data.get('url')
    info = user_data.get('info', {})
    if not url:
        await query.message.reply_text("No URL found in your session. Please resend the link.")
        return

    download_type = 'video'
    format_label = 'standard'
    if data == 'dl_audio':
        download_type = 'audio'
        format_label = 'audio'
    elif data == 'dl_video_low':
        download_type = 'video_low'
        format_label = 'low'
    elif data == 'dl_video_high':
        download_type = 'video_high'
        format_label = 'high'
    else:
        await query.message.reply_text("Unknown option.")
        return

    status = await query.message.reply_text("Starting download...")

    # Create a queue for progress updates
    progress_queue = asyncio.Queue()

    loop = asyncio.get_running_loop()

    def progress_reporter(d):
        # called from yt-dlp thread; push to asyncio queue safely
        loop.call_soon_threadsafe(progress_queue.put_nowait, d)

    # Use a temporary directory for download
    tmpdir = tempfile.mkdtemp(prefix='ytbot_')

    try:
        # run download in thread
        download_task = asyncio.to_thread(
            yt_service.download_with_progress,
            url,
            download_type,
            tmpdir,
            progress_reporter,
            format_label,
        )

        # Start a coroutine that reads progress_queue and edits the status message
        async def progress_watcher():
            last_pct = None
            while True:
                try:
                    d = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    # check if download finished
                    if download_task.done():
                        break
                    continue

                status_text = d.get('status')
                if status_text == 'downloading':
                    pct = d.get('downloaded_bytes') and d.get('total_bytes') and (
                        round(d['downloaded_bytes'] / d['total_bytes'] * 100, 1)
                        if d['total_bytes']
                        else None
                    )
                    if pct is not None and pct != last_pct:
                        last_pct = pct
                        try:
                            await status.edit_text(f"Downloading... {pct}%")
                        except Exception:
                            pass
                elif status_text in ('finished', 'error'):
                    try:
                        await status.edit_text(f"{status_text.capitalize()}.")
                    except Exception:
                        pass

        watcher_task = asyncio.create_task(progress_watcher())

        filename = await download_task
        await watcher_task

        if not filename or not os.path.exists(filename):
            await status.edit_text("Download failed or produced no file.")
            return

        size_bytes = os.path.getsize(filename)
        size_mb = size_bytes / (1024 * 1024)

        if size_mb > MAX_FILE_MB:
            await status.edit_text("File exceeds Telegram size limit. Uploading to S3 and providing a link...")
            # upload to s3
            key = os.path.basename(filename)
            s3_key = await asyncio.to_thread(storage.upload_file_to_s3, filename, key)
            url_link = storage.generate_presigned_url(s3_key)
            await query.message.reply_text(f"File is too large to send here. Download it from: {url_link}")
            await status.delete()
        else:
            await status.edit_text("Sending file via Telegram...")
            with open(filename, 'rb') as f:
                await query.message.reply_document(document=InputFile(f, filename=os.path.basename(filename)))
            await status.delete()

    except Exception as e:
        logger.exception("Download/send failed")
        await status.edit_text(f"Operation failed: {e}")
    finally:
        # cleanup
        try:
            for root, dirs, files in os.walk(tmpdir, topdown=False):
                for name in files:
                    try:
                        os.remove(os.path.join(root, name))
                    except Exception:
                        pass
                for name in dirs:
                    try:
                        os.rmdir(os.path.join(root, name))
                    except Exception:
                        pass
            try:
                os.rmdir(tmpdir)
            except Exception:
                pass
        except Exception:
            pass


if __name__ == '__main__':
    token = config.BOT_TOKEN
    if not token or token == 'YOUR_BOT_TOKEN':
        logger.error('BOT_TOKEN not set. Please configure it in .env or environment.')
        raise SystemExit('BOT_TOKEN not configured')

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info('Starting bot...')
    app.run_polling()
