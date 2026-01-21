import os
from utils import AppContext

class YtDlpConfig:   
    def __init__(self, save_path, use_minimal_bypass=False, cookies_file=None, audio_only=False):
        self.save_path = save_path
        self.use_minimal_bypass = use_minimal_bypass
        self.cookies_file = cookies_file
        self.audio_only = audio_only
        
        # Базовые настройки
        self.opts = {
            "retries": 30,
            "fragment_retries": 30,
            "ffmpeg_location": AppContext.ffmpeg_path,
            "quiet": False,
            "no_warnings": False,
            "ignoreerrors": False,
            "lazy_extractors": False,
            "socket_timeout": 60,
            "http_chunk_size": 10485760,
        }
        
        # Настройки в зависимости от формата
        if audio_only:
            # Настройки для аудио
            self.opts.update({
                "format": "bestaudio/best",
                "outtmpl": os.path.join(save_path, "%(title)s.%(ext)s"),
                "postprocessors": [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '320',
                    },
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    },
                    {
                        'key': 'EmbedThumbnail',
                        'already_have_thumbnail': False,
                    },
                ],
                "writethumbnail": True,
            })
        else:
            # Настройки для видео
            self.opts.update({
                "format": "bestvideo[height<=1080]+bestaudio/best",
                "outtmpl": os.path.join(save_path, "%(title)s.%(ext)s"),
                "merge_output_format": "mp4",
            })
        
        # Дополнительные настройки
        if use_minimal_bypass:
            self.opts["http_headers"] = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
            }
        
        if cookies_file:
            self.opts["cookiefile"] = cookies_file