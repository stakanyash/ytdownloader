import os
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QTextEdit, QFileDialog, QMessageBox, QProgressBar,
    QVBoxLayout, QHBoxLayout, QCheckBox, QGroupBox,
    QComboBox, QListWidget, QRadioButton, QButtonGroup
)

from utils import AppContext
from cookie_manager import CookieManager
from ytdlp_config import YtDlpConfig
from download_worker import DownloadWorker
from download_queue import DownloadQueue
from dns_resolver import DNS_AVAILABLE


class YouTubeDownloader(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("YouTube Downloader")
        self.setFixedSize(700, 800)  # Увеличили высоту

        self.save_path = os.path.join(os.path.expanduser("~"), "Videos")
        self.worker = None
        self.queue = DownloadQueue()
        self.is_downloading = False
        self.cookies_file = None

        self.init_ui()
        self.apply_dark_theme()

    def init_ffmpeg(self):
        self.log("Searching for FFmpeg...")
        
        AppContext.ffmpeg_path = AppContext.find_ffmpeg()
        
        if AppContext.ffmpeg_path:
            self.log(f"FFmpeg found: {AppContext.ffmpeg_path}")
        else:
            self.log("FFmpeg not found")
            self.prompt_ffmpeg_selection()

    def init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)

        url_layout = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("YouTube URL")
        self.url_edit.returnPressed.connect(self.add_to_queue)
        
        self.add_btn = QPushButton("Add to Queue")
        self.add_btn.clicked.connect(self.add_to_queue)
        self.add_btn.setFixedWidth(120)
        
        url_layout.addWidget(self.url_edit)
        url_layout.addWidget(self.add_btn)

        queue_label = QLabel("Download Queue:")
        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(150)
        
        queue_controls = QHBoxLayout()
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_from_queue)
        
        self.clear_btn = QPushButton("Clear Queue")
        self.clear_btn.clicked.connect(self.clear_queue)
        
        self.queue_count_label = QLabel("Videos in queue: 0")
        
        queue_controls.addWidget(self.remove_btn)
        queue_controls.addWidget(self.clear_btn)
        queue_controls.addStretch()
        queue_controls.addWidget(self.queue_count_label)

        self.path_edit = QLineEdit(self.save_path)
        self.path_edit.setReadOnly(True)

        path_btn = QPushButton("Select output path")
        path_btn.clicked.connect(self.select_path)

        # Группа для выбора формата (видео/аудио)
        format_group = QGroupBox("Download Format")
        format_layout = QVBoxLayout()
        
        self.format_button_group = QButtonGroup()
        
        self.video_radio = QRadioButton("Video (MP4, best quality up to 1080p)")
        self.audio_radio = QRadioButton("Audio Only (MP3, best quality)")
        
        self.video_radio.setChecked(True)
        
        self.format_button_group.addButton(self.video_radio)
        self.format_button_group.addButton(self.audio_radio)
        
        format_layout.addWidget(self.video_radio)
        format_layout.addWidget(self.audio_radio)
        format_group.setLayout(format_layout)

        cookies_group = QGroupBox("Browser Cookies")
        cookies_layout = QVBoxLayout()
        
        self.browser_combo = QComboBox()
        self.browser_combo.addItems([
            "Auto (search all)", "Don't use", "Chrome", "Firefox", 
            "Edge", "Opera", "Brave", "Chromium", "Vivaldi"
        ])
        
        cookies_help = QLabel("Helps with private and age-restricted videos.")
        cookies_help.setStyleSheet("color: #888; font-size: 10px;")
        
        cookies_layout.addWidget(self.browser_combo)
        cookies_layout.addWidget(cookies_help)
        cookies_group.setLayout(cookies_layout)

        self.use_bypass_check = QCheckBox("Use minimal bypass (custom headers)")
        self.use_dns_check = QCheckBox("Use alternative DNS (8.8.8.8)")
        self.use_dns_check.setChecked(True)
        
        if not DNS_AVAILABLE:
            self.use_dns_check.setEnabled(False)
            self.use_dns_check.setText("DNS unavailable (install: pip install dnspython)")

        self.current_label = QLabel("Current: None")
        self.current_label.setStyleSheet("color: #58a6ff; font-weight: bold;")

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.progress_bar = QProgressBar()

        self.download_btn = QPushButton("Start Downloads")
        self.download_btn.clicked.connect(self.toggle_download)

        help_btn = QPushButton("?")
        help_btn.setFixedWidth(30)
        help_btn.clicked.connect(self.show_about)

        top = QHBoxLayout()
        top.addWidget(QLabel("YouTube Downloader"))
        top.addStretch()
        top.addWidget(help_btn)

        layout = QVBoxLayout(central)
        layout.addLayout(top)
        layout.addLayout(url_layout)
        layout.addWidget(queue_label)
        layout.addWidget(self.queue_list)
        layout.addLayout(queue_controls)
        layout.addWidget(QLabel("Output path:"))
        layout.addWidget(self.path_edit)
        layout.addWidget(path_btn)
        layout.addWidget(format_group)  # Добавили группу выбора формата
        layout.addWidget(cookies_group)
        layout.addWidget(self.use_bypass_check)
        layout.addWidget(self.use_dns_check)
        layout.addWidget(self.current_label)
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
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #404040;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:selected {
                background-color: #0078d7;
            }
            QComboBox {
                background-color: #1e1e1e;
                border: 1px solid #404040;
                padding: 6px;
                border-radius: 4px;
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
                subcontrol-position: top left;
                padding: 0 5px;
                color: #ffffff;
            }
            QCheckBox {
                spacing: 8px;
                color: #ffffff;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #404040;
                border-radius: 3px;
                background-color: #1e1e1e;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #0078d7;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d7;
                border: 2px solid #0078d7;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTAiIHZpZXdCb3g9IjAgMCAxMiAxMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMSA1TDQgOEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIGZpbGw9Im5vbmUiLz48L3N2Zz4=);
            }
            QRadioButton {
                spacing: 8px;
                color: #ffffff;
                padding: 4px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #505050;
                border-radius: 10px;
                background-color: #1e1e1e;
            }
            QRadioButton::indicator:hover {
                border: 2px solid #0078d7;
                background-color: #2a2a2a;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #0078d7;
                background-color: #1e1e1e;
            }
            QRadioButton::indicator:checked::after {
                width: 10px;
                height: 10px;
                border-radius: 5px;
                background-color: #0078d7;
            }
            QRadioButton:disabled {
                color: #666666;
            }
            QRadioButton::indicator:disabled {
                border: 2px solid #333333;
                background-color: #1a1a1a;
            }
        """)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{timestamp}] {message}")

    def update_queue_count(self):
        count = len(self.queue)
        self.queue_count_label.setText(f"Videos in queue: {count}")
        
        if count == 0:
            self.download_btn.setEnabled(False)
            self.download_btn.setText("Start Downloads (Queue Empty)")
        elif not self.is_downloading:
            self.download_btn.setEnabled(True)
            self.download_btn.setText(f"Start Downloads ({count})")

    def add_to_queue(self):
        url = self.url_edit.text().strip()
        if not url:
            return
        
        if not self.queue.add(url):
            QMessageBox.warning(self, "Duplicate", "This URL is already in the queue!")
            return
        
        self.queue_list.addItem(f"⏳ {url}")
        self.url_edit.clear()
        self.update_queue_count()
        self.log(f"Added to queue: {url}")

    def remove_from_queue(self):
        row = self.queue_list.currentRow()
        if row >= 0:
            url = list(self.queue)[row]
            self.queue.remove(row)
            self.queue_list.takeItem(row)
            self.update_queue_count()
            self.log(f"Removed from queue: {url}")

    def clear_queue(self):
        if len(self.queue) == 0:
            return
        
        reply = QMessageBox.question(
            self, "Clear Queue",
            f"Remove all {len(self.queue)} videos from queue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.queue.clear()
            self.queue_list.clear()
            self.update_queue_count()
            self.log("Queue cleared")

    def select_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Save Directory")
        if path:
            self.save_path = path
            self.path_edit.setText(path)

    def prompt_ffmpeg_selection(self):
        reply = QMessageBox.question(
            self, "FFmpeg Not Found",
            "FFmpeg was not found automatically.\n\n"
            "Without FFmpeg, only limited video formats will be available.\n\n"
            "Would you like to select FFmpeg manually?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Определяем фильтр файлов в зависимости от ОС
            import platform
            if platform.system() == "Windows":
                file_filter = "Executable Files (*.exe);;All Files (*.*)"
            else:
                file_filter = "All Files (*)"
            
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select FFmpeg Executable",
                "/usr/bin" if platform.system() == "Linux" else "",
                file_filter
            )
            
            if file_path and os.path.exists(file_path):
                AppContext.ffmpeg_path = file_path
                self.log(f"FFmpeg manually selected: {file_path}")
                QMessageBox.information(
                    self, 
                    "FFmpeg Selected", 
                    f"FFmpeg has been set to:\n{file_path}"
                )
            else:
                self.log("FFmpeg selection cancelled - limited formats available")
        else:
            self.log("FFmpeg not configured - limited formats available")

    def toggle_download(self):
        if self.is_downloading:
            if self.worker and self.worker.isRunning():
                self.worker.cancel()
                self.download_btn.setEnabled(False)
                self.download_btn.setText("Cancelling...")
        else:
            self.start_queue_download()

    def start_queue_download(self):
        if len(self.queue) == 0:
            return

        self.is_downloading = True
        self.log_box.clear()
        self.log(f"Starting queue download: {len(self.queue)} videos")
        
        # Определяем формат
        download_audio_only = self.audio_radio.isChecked()
        if download_audio_only:
            self.log("Format: Audio Only (MP3)")
        else:
            self.log("Format: Video (MP4, up to 1080p)")
        
        browser_map = {
            0: "auto", 1: "none", 2: "chrome", 3: "firefox",
            4: "edge", 5: "opera", 6: "brave", 7: "chromium", 8: "vivaldi"
        }
        browser_choice = browser_map[self.browser_combo.currentIndex()]
        self.cookies_file = CookieManager.extract(browser_choice, log_callback=self.log)

        self.add_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.url_edit.setEnabled(False)
        self.video_radio.setEnabled(False)
        self.audio_radio.setEnabled(False)
        
        self.download_btn.setText("Cancel Queue")
        self.download_btn.setStyleSheet(
            "QPushButton { background-color: #d7000f; } "
            "QPushButton:hover { background-color: #ff0000; }"
        )
        
        self.process_next_in_queue()

    def process_next_in_queue(self):
        if len(self.queue) == 0 or not self.is_downloading:
            self.finish_queue_download()
            return

        url = self.queue.peek()
        self.log(f"\n{'='*50}")
        self.log(f"Processing: {url}")
        self.log(f"Remaining: {len(self.queue)} videos")
        self.log(f"{'='*50}\n")
        
        self.queue_list.item(0).setText(f"⬇️ {url}")
        self.current_label.setText(f"Current: {url[:60]}...")
        self.progress_bar.setValue(0)

        # Передаём информацию о формате в конфигурацию
        download_audio_only = self.audio_radio.isChecked()
        
        config = YtDlpConfig(
            save_path=self.save_path,
            use_minimal_bypass=self.use_bypass_check.isChecked(),
            cookies_file=self.cookies_file,
            audio_only=download_audio_only  # Новый параметр
        )

        self.worker = DownloadWorker(url, config, self.use_dns_check.isChecked())
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(lambda v: self.progress_bar.setValue(int(v)))
        self.worker.finished_signal.connect(self.download_finished)
        self.worker.current_video_signal.connect(
            lambda title: self.current_label.setText(f"Current: {title[:60]}...")
        )
        self.worker.start()

    def download_finished(self, success, message):
        current_url = self.queue.next()
        
        if current_url:
            self.queue_list.takeItem(0)
            self.update_queue_count()
        
        if success:
            self.log(f"✓ Successfully downloaded: {current_url}\n")
        else:
            self.log(f"✗ Failed: {current_url}")
            self.log(f"Error: {message}\n")
            
            if len(self.queue) > 0 and "cancelled" not in message.lower():
                reply = QMessageBox.question(
                    self, "Download Failed",
                    f"Failed to download video.\n\n{len(self.queue)} videos remaining.\n\nContinue?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    self.is_downloading = False
        
        self.progress_bar.setValue(0)
        
        if self.is_downloading and len(self.queue) > 0:
            self.process_next_in_queue()
        else:
            self.finish_queue_download()

    def finish_queue_download(self):
        self.is_downloading = False
        self.current_label.setText("Current: None")
        
        if self.cookies_file and os.path.exists(self.cookies_file):
            try:
                os.remove(self.cookies_file)
            except:
                pass
        
        self.add_btn.setEnabled(True)
        self.remove_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.url_edit.setEnabled(True)
        self.video_radio.setEnabled(True)
        self.audio_radio.setEnabled(True)
        
        self.download_btn.setStyleSheet("")
        self.update_queue_count()
        
        self.log("\n" + "="*50)
        self.log("Queue processing finished!")
        self.log("="*50)
        
        QMessageBox.information(self, "Complete", "All downloads finished!")

    def show_about(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("About")
        msg.setTextFormat(Qt.RichText)
        
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
        
        link_style = "color: #58a6ff; text-decoration: none;"
        
        msg.setText(
            "<h3>YouTube Downloader v1.2</h3>"
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