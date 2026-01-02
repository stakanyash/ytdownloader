import re
from PyQt5.QtCore import QThread, pyqtSignal
import yt_dlp
from utils import strip_ansi
from dns_resolver import DnsResolver

class DownloadWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(float)
    finished_signal = pyqtSignal(bool, str)
    current_video_signal = pyqtSignal(str)

    def __init__(self, url, config, use_custom_dns=True):
        super().__init__()
        self.url = url
        self.config = config
        self.use_custom_dns = use_custom_dns
        self._is_cancelled = False
        self.dns_resolver = None

    def cancel(self):
        self._is_cancelled = True
        self.log("Cancelling download...")

    def log(self, message):
        self.log_signal.emit(strip_ansi(message))

    def progress_hook(self, d):
        if self._is_cancelled:
            raise Exception("Download cancelled by user")
            
        if d["status"] == "downloading":
            if "downloaded_bytes" in d and "total_bytes" in d:
                percent = (d["downloaded_bytes"] / d["total_bytes"]) * 100
                self.progress_signal.emit(percent)
            elif "downloaded_bytes" in d and "total_bytes_estimate" in d:
                percent = (d["downloaded_bytes"] / d["total_bytes_estimate"]) * 100
                self.progress_signal.emit(percent)
            elif "_percent_str" in d:
                percent_str = re.sub(r"[^\d.]", "", d.get("_percent_str", ""))
                if percent_str:
                    try:
                        self.progress_signal.emit(float(percent_str))
                    except:
                        pass

        elif d["status"] == "finished":
            self.progress_signal.emit(100.0)
            self.log("Download finished. Merging...")

    def run(self):
        if self.use_custom_dns:
            self.dns_resolver = DnsResolver(log_callback=self.log)
            self.dns_resolver.enable()

        try:
            opts = self.config.opts.copy()
            opts["progress_hooks"] = [self.progress_hook]
            
            self.log("Starting download...")
            self.log(f"URL: {self.url}")

            with yt_dlp.YoutubeDL(opts) as ydl:
                self.log("Fetching video information...")
                info = ydl.extract_info(self.url, download=False)
                
                if self._is_cancelled:
                    self.finished_signal.emit(False, "Download cancelled by user")
                    return
                
                video_title = info.get('title', 'Unknown')
                self.current_video_signal.emit(video_title)
                
                self.log(f"Video: {video_title}")
                self.log(f"Duration: {info.get('duration', 0)} sec")
                self.log(f"Uploader: {info.get('uploader', 'Unknown')}")
                
                self.log("Starting download...")
                ydl.download([self.url])

            if self._is_cancelled:
                self.finished_signal.emit(False, "Download cancelled by user")
            else:
                self.finished_signal.emit(True, "Download completed successfully!")

        except Exception as e:
            if self._is_cancelled or "cancelled by user" in str(e).lower():
                self.finished_signal.emit(False, "Download cancelled by user")
            else:
                error_text = strip_ansi(str(e))
                
                if "403" in error_text or "Forbidden" in error_text:
                    suggestion = (
                        "\n\nLooks like ISP blocking:\n"
                        "1. Try different bypass method\n"
                        "2. Make sure GoodbyeDPI/Zapret is running\n"
                        "3. Check if video opens in browser"
                    )
                    error_text += suggestion
                
                self.log(f"ERROR: {error_text}")
                self.finished_signal.emit(False, error_text)

        finally:
            if self.dns_resolver:
                self.dns_resolver.disable()