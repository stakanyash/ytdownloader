import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import sys
import json
import shutil
import tempfile
import win32crypt
from base64 import b64decode
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import sqlite3
import yt_dlp
import subprocess
import winreg
from datetime import datetime
import re

class YouTubeDownloaderApp:
    def __init__(self, root):  
        self.root = root
        self.root.title("YouTube Downloader")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        icon_path = self.resource_path("app.ico")
        self.root.iconbitmap(icon_path)

        self.create_widgets()
        self.position_widgets()

        self.save_path = os.path.expanduser("~\\Videos")
        self.cookies_loaded = False
        self.ffmpeg_path = None

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def create_widgets(self):
        # URL Entry
        self.url_frame = ttk.Frame(self.root)
        self.url_label = ttk.Label(self.url_frame, text="YouTube URL:")
        self.url_entry = ttk.Entry(self.url_frame, width=40)

        # Save Path
        self.path_frame = ttk.Frame(self.root)
        self.path_label = ttk.Label(self.path_frame, text="Output path:")
        self.path_entry = ttk.Entry(self.path_frame, width=40)
        self.path_btn = ttk.Button(self.path_frame, text="Select output path", command=self.select_save_path)

        # Log Window
        self.log_text = tk.Text(self.root, height=15, width=70, state='disabled', wrap='word')
        self.log_scroll = ttk.Scrollbar(self.root, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.log_scroll.set)

        # Progress Bar
        self.progress_bar = ttk.Progressbar(self.root, mode="determinate", length=500)

        # Download Button
        self.download_btn = ttk.Button(self.root, text="Download", command=self.start_download)

        # Info button
        self.help_btn = ttk.Button(self.root, text="?", width=3, command=self.show_help_info)


    def position_widgets(self):
        # Grid Layout
        # YouTube URL
        self.url_frame.grid(row=0, column=0, padx=10, pady=5, sticky='ew')

        # Кнопка помощи
        self.help_btn.grid(row=0, column=2, padx=5, pady=5, sticky='e')
        self.url_label.pack(anchor='w', padx=5, pady=(5, 0))  # Метка слева сверху
        self.url_entry.pack(fill='x', padx=5, pady=(0, 5))    # Поле ввода растягивается

        # Output Path
        self.path_frame.grid(row=1, column=0, padx=10, pady=5, sticky='ew', columnspan=2)
        self.path_label.pack(anchor='w', padx=5, pady=(5, 0))  # Метка слева сверху
        self.path_entry.pack(fill='x', padx=5, pady=(0, 5))    # Поле ввода растягивается
        self.path_btn.pack(pady=(0, 10))                       # Кнопка под полем

        # Log Window
        self.log_text.grid(row=2, column=0, padx=10, pady=10, sticky='nsew', columnspan=2)
        self.log_scroll.grid(row=2, column=2, padx=0, pady=10, sticky='ns')

        # Progress Bar
        self.progress_bar.grid(row=3, column=0, padx=10, pady=10, sticky='ew', columnspan=2)

        # Download Button
        self.download_btn.grid(row=4, column=0, padx=10, pady=10, columnspan=2, sticky='ew')
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

    def log(self, message):
        self.log_text.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.config(state='disabled')
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def show_help_info(self):
        help_text = (
            "YouTube Downloader v0.1\n"
            "Author: stakan\n\n"
            "This program was originally developed for my personal use to download videos from YouTube.\n\n"
            "To use this application, you need:\n"
            "- Be logged into YouTube via Microsoft Edge\n"
            "- FFmpeg must be installed\n"
            "\n"
            "This program uses tkinter as GUI."
        )
        messagebox.showinfo("About", help_text)

    def select_save_path(self):
        path = filedialog.askdirectory(title="Select Save Directory")
        if path:
            self.save_path = path
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)

    def get_edge_cookies(self):
        self.log("Extracting cookies from Microsoft Edge...")
        try:
            return self._get_windows_edge_cookies()
        except Exception as e:
            self.log(f"Cookie extraction error: {str(e)}")
            return {}

    def _get_windows_edge_cookies(self):
        appdata = os.getenv("LOCALAPPDATA")
        edge_path = os.path.join(appdata, "Microsoft", "Edge", "User Data")
        
        if not os.path.exists(edge_path):
            self.log("Edge installation not found")
            return {}

        # Get encryption key
        local_state_path = os.path.join(edge_path, "Local State")
        if not os.path.exists(local_state_path):
            self.log("Local State file missing")
            return {}

        with open(local_state_path, 'r', encoding='utf-8') as f:
            local_state = json.load(f)
        
        encrypted_key = b64decode(local_state["os_crypt"]["encrypted_key"])
        encrypted_key = encrypted_key[5:]  # Remove DPAPI prefix
        decrypted_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

        cookies = []
        profiles = ["Default"] + [f"Profile {i}" for i in range(1, 6)]

        for profile in profiles:
            profile_dir = os.path.join(edge_path, profile)
            if not os.path.exists(profile_dir):
                continue

            cookies_db = os.path.join(profile_dir, "Network", "Cookies")
            if not os.path.exists(cookies_db):
                continue

            try:
                temp_db = os.path.join(tempfile.gettempdir(), f"edge_cookies_{os.getpid()}.db")
                shutil.copy2(cookies_db, temp_db)

                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT host_key, name, path, 
                    encrypted_value, expires_utc 
                    FROM cookies""")

                for host_key, name, path, encrypted_value, expires in cursor.fetchall():
                    if not encrypted_value:
                        continue

                    try:
                        # Handle different encryption schemes
                        if encrypted_value.startswith(b'v10') or encrypted_value.startswith(b'v11'):
                            nonce = encrypted_value[3:15]
                            ciphertext = encrypted_value[15:-16]
                            tag = encrypted_value[-16:]
                            
                            cipher = AESGCM(decrypted_key)
                            decrypted = cipher.decrypt(nonce, ciphertext + tag, None)
                        else:
                            decrypted = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1]
                            
                        cookies.append({
                            'domain': host_key,
                            'name': name,
                            'path': path,
                            'value': decrypted.decode(errors='replace'),
                            'expires': expires,
                            'httpOnly': False,
                            'secure': False
                        })
                    except Exception as e:
                        continue

                conn.close()
                os.remove(temp_db)
            except Exception as e:
                self.log(f"Error processing {profile} cookies: {str(e)}")
                continue

        self.log(f"Successfully loaded {len(cookies)} cookies")
        return cookies

    def write_cookies_to_file(self, cookies, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# https://curl.haxx.se/docs/http-cookies.html\n\n")
                
                for cookie in cookies:
                    f.write("\t".join([
                        cookie['domain'],
                        "TRUE",
                        cookie['path'],
                        "TRUE" if cookie['secure'] else "FALSE",
                        str(int(cookie['expires'])),
                        cookie['name'],
                        cookie['value']
                    ]) + "\n")
            self.log(f"Cookies saved to {filename}")
        except Exception as e:
            self.log(f"Error saving cookies: {str(e)}")

    def get_ffmpeg_location(self):
        """Multi-method ffmpeg detection"""
        self.log("Searching for ffmpeg...")
        
        # Check PATH
        try:
            ffmpeg_path = shutil.which('ffmpeg')
            if ffmpeg_path:
                self.log(f"Found in PATH: {ffmpeg_path}")
                return ffmpeg_path
        except Exception as e:
            self.log(f"PATH search error: {str(e)}")

        # Check common locations
        common_paths = [
            os.path.join(os.getcwd(), 'ffmpeg', 'bin', 'ffmpeg.exe'),
            os.path.expanduser('~\\ffmpeg\\bin\\ffmpeg.exe'),
            'C:\\ffmpeg\\bin\\ffmpeg.exe',
            'C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe',
            'C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe'
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                self.log(f"Found in default location: {path}")
                return path

        # Check registry
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\ffmpeg.exe"
            ) as key:
                reg_path, _ = winreg.QueryValueEx(key, "")
                if os.path.exists(reg_path):
                    self.log(f"Found in registry: {reg_path}")
                    return reg_path
        except Exception as e:
            self.log(f"Registry search failed: {str(e)}")

        self.log("FFmpeg not found! Some functions may be limited.")
        return None

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '0%').strip()
            percent_str = re.sub(r'\x1b$$[0-9;]*m', '', percent_str)  # Удаляем ANSI-цвета
            percent_str = re.sub(r'[^\d.]', '', percent_str)  # Оставляем только цифры и точку
            
            try:
                percent = float(percent_str)
            except ValueError:
                self.log(f"Invalid percent value: {percent_str}")
                return
                
            speed = d.get('_speed_str', '0 KiB/s').strip()
            eta = d.get('_eta_str', 'Unknown').strip()
            
            self.progress_bar['value'] = percent
            self.log(f"Downloading: {percent_str}% at {speed}, ETA: {eta}")
        elif d['status'] == 'finished':
            self.log("Download completed, converting video...")

    def download_video(self, url):
        try:
            self.progress_bar['value'] = 0
            self.ffmpeg_path = self.get_ffmpeg_location()

            # Extract cookies
            cookies = self.get_edge_cookies()
            cookies_file = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
            self.write_cookies_to_file(cookies, cookies_file)

            # yt-dlp configuration
            ydl_opts = {
                'format': 'bestvideo[height<=1080][fps<=60]+bestaudio/best[height<=1080]',
                'outtmpl': os.path.join(self.save_path, '%(title)s.%(ext)s'),
                'progress_hooks': [self.progress_hook],
                'cookiefile': cookies_file if cookies else None,
                'noplaylist': True,
                'merge_output_format': 'mp4',
                'retries': 10,
                'fragment_retries': 10,
                'ffmpeg_location': self.ffmpeg_path,
                'postprocessor_args': ['-threads', '4'],
                'logger': self.YTDLLogger(self),
            }

            if not self.ffmpeg_path:
                self.log("Warning: FFmpeg not found - limited format support")

            self.log("Starting download process...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.log("Download completed successfully!")
            messagebox.showinfo("Success", "Download completed!")

        except Exception as e:
            error_msg = str(e)
            if "ffmpeg" in error_msg.lower():
                error_msg += "\n\nPlease install FFmpeg and add it to PATH or program directory"
            self.log(f"ERROR: {error_msg}")
            messagebox.showerror("Error", error_msg)
        finally:
            self.progress_bar['value'] = 0

    class YTDLLogger:
        def __init__(self, gui):
            self.gui = gui

        def debug(self, msg):
            if msg.startswith('[debug]'):
                return
            self.gui.log(msg)

        def warning(self, msg):
            self.gui.log(f"WARNING: {msg}")

        def error(self, msg):
            self.gui.log(f"ERROR: {msg}")

    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Input Error", "Please enter a valid URL")
            return

        # Clear logs
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')

        # Start download thread
        thread = threading.Thread(target=self.download_video, args=(url,), daemon=True)
        thread.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()