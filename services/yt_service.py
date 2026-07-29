import os
from yt_dlp import YoutubeDL
import yt_dlp

def extract_video_info(url: str) -> dict:
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title', 'video'),
            'duration': info.get('duration', 0),
            'id': info.get('id'),
        }

def download_with_progress(url: str, download_type: str, out_dir: str, progress_reporter, quality_label: str = 'standard') -> str:
    """
    Downloads the media using yt-dlp and reports progress via progress_reporter(dict).

    progress_reporter will be called from the download thread; it should be thread-safe (we use loop.call_soon_threadsafe in the caller).

    Returns the full path to the downloaded file.
    """
    os.makedirs(out_dir, exist_ok=True)
    template = os.path.join(out_dir, '%(title)s_%(id)s.%(ext)s')

    # determine format options based on type
    if download_type == 'audio':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        # video: choose lower or higher quality
        if download_type == 'video_low':
            fmt = 'worstvideo[ext=mp4]+bestaudio/best'
        elif download_type == 'video_high':
            fmt = 'bestvideo[ext=mp4]+bestaudio/best'
        else:
            fmt = 'best[ext=mp4]/best'
        ydl_opts = {
            'format': fmt,
            'outtmpl': template,
            'merge_output_format': 'mp4',
            'noplaylist': True,
        }

    def _hook(d):
        try:
            progress_reporter(d)
        except Exception:
            pass

    ydl_opts['progress_hooks'] = [_hook]

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # if audio postprocessor changed extension to mp3
        if download_type == 'audio':
            filename = os.path.splitext(filename)[0] + '.mp3'
        return filename
