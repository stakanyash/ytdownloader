import sys
import os
import re
import shutil
import tempfile
import winreg
from datetime import datetime

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QLabel, QLineEdit, QPushButton,
    QTextEdit, QFileDialog, QMessageBox,
    QProgressBar, QVBoxLayout, QHBoxLayout,
    QCheckBox, QGroupBox, QComboBox
)

import yt_dlp
import browser_cookie3
import socket

try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False


# ================= ANSI CLEANER =================

def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)


# ================= DOWNLOAD THREAD =================

class DownloadWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(float)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, url, save_path, use_minimal_bypass=False, browser_choice="auto", use_custom_dns=True):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.use_minimal_bypass = use_minimal_bypass
        self.browser_choice = browser_choice
        self.use_custom_dns = use_custom_dns
        self._is_cancelled = False

    def cancel(self):
        """Cancel the download"""
        self._is_cancelled = True
        self.log("Cancelling download...")

    def log(self, message):
        self.log_signal.emit(strip_ansi(message))

    def get_ffmpeg_location(self):
        self.log("Searching for ffmpeg...")

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            self.log(f"Found ffmpeg in PATH: {ffmpeg}")
            return ffmpeg

        common_paths = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe"
        ]

        for path in common_paths:
            if os.path.exists(path):
                self.log(f"Found ffmpeg: {path}")
                return path

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\ffmpeg.exe"
            ) as key:
                reg_path, _ = winreg.QueryValueEx(key, "")
                if os.path.exists(reg_path):
                    self.log(f"Found ffmpeg in registry: {reg_path}")
                    return reg_path
        except:
            pass

        self.log("FFmpeg not found!")
        return None

    def progress_hook(self, d):
        if self._is_cancelled:
            raise Exception("Download cancelled by user")
            
        if d["status"] == "downloading":
            # Get download percentage
            if "downloaded_bytes" in d and "total_bytes" in d:
                percent = (d["downloaded_bytes"] / d["total_bytes"]) * 100
                self.progress_signal.emit(percent)
            elif "downloaded_bytes" in d and "total_bytes_estimate" in d:
                percent = (d["downloaded_bytes"] / d["total_bytes_estimate"]) * 100
                self.progress_signal.emit(percent)
            elif "_percent_str" in d:
                percent_str = d.get("_percent_str", "")
                percent_str = re.sub(r"[^\d.]", "", percent_str)
                if percent_str:
                    try:
                        self.progress_signal.emit(float(percent_str))
                    except:
                        pass

        elif d["status"] == "finished":
            self.progress_signal.emit(100.0)
            self.log("Download finished. Merging...")
            
        elif d["status"] == "error":
            self.log(f"Download error: {d.get('error', 'Unknown error')}")

    def run(self):
        cookies_file = None
        original_getaddrinfo = None
        
        # Setup custom DNS to bypass ISP blocking
        if self.use_custom_dns and DNS_AVAILABLE:
            self.log("Setting up custom DNS (8.8.8.8, 1.1.1.1)...")
            original_getaddrinfo = socket.getaddrinfo
            
            def custom_getaddrinfo(host, port, family=0, socktype=0, proto=0, flags=0):
                """Use Google/Cloudflare DNS to bypass ISP blocking"""
                if 'youtube.com' in host or 'googlevideo.com' in host or 'ytimg.com' in host:
                    try:
                        resolver = dns.resolver.Resolver()
                        resolver.nameservers = ['8.8.8.8', '1.1.1.1', '8.8.4.4']  # Google and Cloudflare
                        resolver.timeout = 5
                        resolver.lifetime = 5
                        
                        # Try A record (IPv4)
                        try:
                            answers = resolver.resolve(host, 'A')
                            ip = str(answers[0])
                            self.log(f"DNS resolved: {host} -> {ip}")
                            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port))]
                        except:
                            # If IPv4 fails, try IPv6
                            try:
                                answers = resolver.resolve(host, 'AAAA')
                                ip = str(answers[0])
                                self.log(f"DNS resolved (IPv6): {host} -> {ip}")
                                return [(socket.AF_INET6, socket.SOCK_STREAM, 6, '', (ip, port, 0, 0))]
                            except:
                                pass
                    except Exception as e:
                        self.log(f"Custom DNS failed for {host}: {e}")
                
                # Fallback to system DNS
                return original_getaddrinfo(host, port, family, socktype, proto, flags)
            
            socket.getaddrinfo = custom_getaddrinfo
            self.log("Custom DNS enabled")
        elif self.use_custom_dns and not DNS_AVAILABLE:
            self.log("WARNING: dnspython not installed, custom DNS disabled")
            self.log("Install: pip install dnspython")

        try:
            # Extract cookies
            if self.browser_choice != "none":
                self.log(f"Extracting cookies from {self.browser_choice}...")
                try:
                    cookies = None
                    
                    if self.browser_choice == "auto":
                        # Auto search in popular browsers
                        browsers = [
                            ('Chrome', lambda: browser_cookie3.chrome(domain_name="youtube.com")),
                            ('Firefox', lambda: browser_cookie3.firefox(domain_name="youtube.com")),
                            ('Edge', lambda: browser_cookie3.edge(domain_name="youtube.com")),
                            ('Opera', lambda: browser_cookie3.opera(domain_name="youtube.com")),
                            ('Brave', lambda: browser_cookie3.brave(domain_name="youtube.com")),
                        ]
                        
                        for browser_name, browser_func in browsers:
                            try:
                                cookies = browser_func()
                                self.log(f"✓ Cookies found in {browser_name}")
                                break
                            except:
                                continue
                                
                        if not cookies:
                            self.log("No cookies found in any browser")
                    else:
                        # Specific browser
                        browser_functions = {
                            'chrome': browser_cookie3.chrome,
                            'firefox': browser_cookie3.firefox,
                            'edge': browser_cookie3.edge,
                            'opera': browser_cookie3.opera,
                            'brave': browser_cookie3.brave,
                            'chromium': browser_cookie3.chromium,
                            'vivaldi': browser_cookie3.vivaldi,
                        }
                        
                        if self.browser_choice in browser_functions:
                            try:
                                cookies = browser_functions[self.browser_choice](domain_name="youtube.com")
                                self.log(f"✓ Cookies extracted from {self.browser_choice.title()}")
                            except Exception as e:
                                self.log(f"Failed to extract cookies from {self.browser_choice.title()}: {e}")
                    
                    if cookies:
                        cookies_file = os.path.join(
                            tempfile.gettempdir(), "yt_cookies.txt"
                        )

                        with open(cookies_file, "w", encoding="utf-8") as f:
                            f.write("# Netscape HTTP Cookie File\n")
                            for c in cookies:
                                f.write("\t".join([
                                    c.domain,
                                    "TRUE" if c.domain.startswith(".") else "FALSE",
                                    c.path,
                                    "TRUE" if c.secure else "FALSE",
                                    str(c.expires or 0),
                                    c.name,
                                    c.value
                                ]) + "\n")
                        self.log("Cookies saved successfully")
                        
                except Exception as e:
                    self.log(f"Cookie extraction failed: {e}")
                    cookies_file = None
            else:
                self.log("Skipping cookie extraction (disabled)")

            ffmpeg = self.get_ffmpeg_location()

            # Base yt-dlp options
            ydl_opts = {
                "format": "bestvideo[height<=1080]+bestaudio/best",
                "outtmpl": os.path.join(
                    self.save_path, "%(title)s.%(ext)s"
                ),
                "progress_hooks": [self.progress_hook],
                "merge_output_format": "mp4",
                "retries": 30,
                "fragment_retries": 30,
                "ffmpeg_location": ffmpeg,
                "quiet": False,
                "no_warnings": False,
                "ignoreerrors": False,
                "lazy_extractors": False,
                # Increased timeouts to bypass DPI
                "socket_timeout": 60,
                "http_chunk_size": 10485760,  # 10MB chunks
            }

            # Add minimal bypass if enabled
            if self.use_minimal_bypass:
                self.log("Using minimal bypass (custom headers)")
                ydl_opts["http_headers"] = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-us,en;q=0.5",
                }
            else:
                self.log("Using standard download mode")

            # Add cookies
            if cookies_file:
                ydl_opts["cookiefile"] = cookies_file
                self.log("Using browser cookies for authentication")

            if not ffmpeg:
                self.log("Warning: FFmpeg not found (limited formats)")

            self.log("Starting download...")
            self.log(f"URL: {self.url}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # First get video info
                self.log("Fetching video information...")
                info = ydl.extract_info(self.url, download=False)
                
                if self._is_cancelled:
                    self.finished_signal.emit(False, "Download cancelled by user")
                    return
                    
                self.log(f"✓ Video: {info.get('title', 'Unknown')}")
                self.log(f"✓ Duration: {info.get('duration', 0)} sec")
                self.log(f"✓ Uploader: {info.get('uploader', 'Unknown')}")
                
                # Then download
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
                
                # Analyze error
                if "403" in error_text or "Forbidden" in error_text:
                    suggestion = (
                        "\n\nLooks like ISP blocking:\n"
                        "1. Try different bypass method\n"
                        "2. Make sure GoodbyeDPI/Zapret is running\n"
                        "3. Check if video opens in browser\n"
                        "4. Try updating yt-dlp: pip install -U yt-dlp"
                    )
                    self.log(f"ERROR: {error_text}{suggestion}")
                    self.finished_signal.emit(False, error_text + suggestion)
                else:
                    self.log(f"ERROR: {error_text}")
                    self.finished_signal.emit(False, error_text)

        finally:
            # Restore original DNS
            if original_getaddrinfo:
                socket.getaddrinfo = original_getaddrinfo
                self.log("Restored original DNS")
            
            if cookies_file and os.path.exists(cookies_file):
                try:
                    os.remove(cookies_file)
                except:
                    pass


# ================= MAIN WINDOW =================

class YouTubeDownloader(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("YouTube Downloader")
        self.setFixedSize(540, 640)

        self.save_path = os.path.join(os.path.expanduser("~"), "Videos")
        self.worker = None

        self.init_ui()
        self.apply_dark_theme()

    def init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)

        # URL input
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("YouTube URL")

        # Path selection
        self.path_edit = QLineEdit(self.save_path)
        self.path_edit.setReadOnly(True)

        path_btn = QPushButton("Select output path")
        path_btn.clicked.connect(self.select_path)

        # Browser cookies group
        cookies_group = QGroupBox("Browser Cookies")
        cookies_layout = QVBoxLayout()
        
        self.browser_combo = QComboBox()
        self.browser_combo.addItems([
            "Auto (search all)",
            "Don't use",
            "Chrome",
            "Firefox", 
            "Edge",
            "Opera",
            "Brave",
            "Chromium",
            "Vivaldi"
        ])
        
        cookies_help = QLabel(
            "Helps with private and age-restricted videos.\n"
            "Select the browser where you're logged into YouTube."
        )
        cookies_help.setWordWrap(True)
        cookies_help.setStyleSheet("color: #888; font-size: 10px;")
        
        cookies_layout.addWidget(self.browser_combo)
        cookies_layout.addWidget(cookies_help)
        cookies_group.setLayout(cookies_layout)

        # Bypass settings
        self.use_bypass_check = QCheckBox("Use minimal bypass (custom headers)")
        self.use_bypass_check.setChecked(False)
        self.use_bypass_check.setToolTip("Adds browser headers to bypass blocking")

        # DNS settings
        self.use_dns_check = QCheckBox("Use alternative DNS (8.8.8.8)")
        self.use_dns_check.setChecked(True)
        self.use_dns_check.setToolTip("Bypass ISP DNS blocking")
        
        if not DNS_AVAILABLE:
            self.use_dns_check.setEnabled(False)
            self.use_dns_check.setText("❌ DNS unavailable (install: pip install dnspython)")
            self.use_dns_check.setStyleSheet("color: #ff6b6b;")

        # Log box
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        # Buttons
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.toggle_download)

        help_btn = QPushButton("?")
        help_btn.setFixedWidth(30)
        help_btn.clicked.connect(self.show_about)

        # Layout
        top = QHBoxLayout()
        top.addWidget(QLabel("YouTube URL:"))
        top.addStretch()
        top.addWidget(help_btn)

        layout = QVBoxLayout(central)
        layout.addLayout(top)
        layout.addWidget(self.url_edit)
        layout.addWidget(QLabel("Output path:"))
        layout.addWidget(self.path_edit)
        layout.addWidget(path_btn)
        layout.addWidget(cookies_group)
        layout.addWidget(self.use_bypass_check)
        layout.addWidget(self.use_dns_check)
        layout.addWidget(self.log_box)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.download_btn)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: Segoe UI;
            }
            QLineEdit, QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #404040;
                padding: 6px;
                border-radius: 4px;
            }
            QComboBox {
                background-color: #1e1e1e;
                border: 1px solid #404040;
                padding: 6px;
                border-radius: 4px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #ffffff;
                margin-right: 8px;
            }
            QPushButton {
                background-color: #404040;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #666666;
            }
            QProgressBar {
                border: 1px solid #404040;
                text-align: center;
                height: 18px;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
                border-radius: 3px;
            }
            QGroupBox {
                border: 1px solid #404040;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #404040;
                border-radius: 3px;
                background-color: #1e1e1e;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d7;
            }
        """)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{timestamp}] {message}")

    def select_path(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Save Directory"
        )
        if path:
            self.save_path = path
            self.path_edit.setText(path)

    def toggle_download(self):
        if self.worker and self.worker.isRunning():
            # Cancel download
            self.worker.cancel()
            self.download_btn.setEnabled(False)
            self.download_btn.setText("Cancelling...")
        else:
            # Start download
            self.start_download()

    def start_download(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter YouTube URL")
            return

        self.log_box.clear()
        self.progress_bar.setValue(0)

        use_minimal_bypass = self.use_bypass_check.isChecked()
        use_custom_dns = self.use_dns_check.isChecked()
        
        # Determine browser for cookies
        browser_map = {
            0: "auto",
            1: "none",
            2: "chrome",
            3: "firefox",
            4: "edge",
            5: "opera",
            6: "brave",
            7: "chromium",
            8: "vivaldi"
        }
        browser_choice = browser_map[self.browser_combo.currentIndex()]

        self.worker = DownloadWorker(url, self.save_path, use_minimal_bypass, browser_choice, use_custom_dns)
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(
            lambda v: self.progress_bar.setValue(int(v))
        )
        self.worker.finished_signal.connect(self.download_finished)
        self.worker.start()
        
        # Change button to cancel mode
        self.download_btn.setText("Cancel")
        self.download_btn.setStyleSheet("QPushButton { background-color: #d7000f; } QPushButton:hover { background-color: #ff0000; }")

    def download_finished(self, success, message):
        # Reset button to download mode
        self.download_btn.setText("Download")
        self.download_btn.setEnabled(True)
        self.download_btn.setStyleSheet("")
        
        # Reset progress bar
        self.progress_bar.setValue(0)
        
        if success:
            QMessageBox.information(self, "Success", message)
        else:
            if "cancelled" in message.lower():
                QMessageBox.information(self, "Cancelled", message)
            else:
                QMessageBox.critical(self, "Error", message)

    def show_about(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("About")
        msg.setTextFormat(Qt.RichText)
        
        # Apply dark theme to message box
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                background-color: #2b2b2b;
            }
            QPushButton {
                background-color: #404040;
                color: #ffffff;
                padding: 6px 16px;
                border-radius: 4px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        
        # Use inline styles for links to ensure they work
        link_style = "color: #58a6ff; text-decoration: none;"
        
        msg.setText(
            "<h3>YouTube Downloader v1.0</h3>"
            f"<p><b>Author:</b> stakan<br>"
            f"<a href='https://github.com/stakanyash' style='{link_style}'>github.com/stakanyash</a></p>"
            f"<p><b>Built with:</b><br>"
            f"• <a href='https://www.python.org/' style='{link_style}'>Python</a><br>"
            f"• <a href='https://riverbankcomputing.com/software/pyqt/' style='{link_style}'>PyQt5</a><br>"
            f"• <a href='https://github.com/yt-dlp/yt-dlp' style='{link_style}'>yt-dlp</a><br>"
            f"• <a href='https://github.com/borisbabic/browser_cookie3' style='{link_style}'>browser-cookie3</a><br>"
            f"• <a href='https://github.com/rthalley/dnspython' style='{link_style}'>dnspython</a></p>"
            f"<p><b>Requirements:</b><br>"
            f"• <a href='https://ffmpeg.org/download.html' style='{link_style}'>FFmpeg</a> must be in system PATH</p>"
        )
        msg.exec_()


# ================= ENTRY POINT =================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeDownloader()
    window.show()
    sys.exit(app.exec_())