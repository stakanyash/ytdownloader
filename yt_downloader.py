import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import shutil
import tempfile
import winreg
from datetime import datetime
import re
import browser_cookie3
import yt_dlp

class YouTubeDownloaderApp:
    def __init__(self, root):  
        self.root = root
        self.root.title("YouTube Downloader")
        self.root.geometry("500x500")
        self.root.resizable(False, False)

        self.create_widgets()
        self.position_widgets()

        self.save_path = os.path.expanduser("~\\Videos")
        self.cookies_loaded = False
        self.ffmpeg_path = None

    def create_widgets(self):
        self.url_frame = ttk.Frame(self.root)
        self.url_label = ttk.Label(self.url_frame, text="YouTube URL:")
        self.url_entry = ttk.Entry(self.url_frame, width=40)

        style = ttk.Style()
        style.configure("White.TEntry", fieldbackground="white")

        self.path_frame = ttk.Frame(self.root)
        self.path_label = ttk.Label(self.path_frame, text="Output path:")
        self.path_entry = tk.Entry(self.path_frame, width=40, state='readonly', bg='white', fg='black')
        self.path_btn = ttk.Button(self.path_frame, text="Select output path", command=self.select_save_path)

        self.log_text = tk.Text(
            self.root,
            height=15,
            width=70,
            state='disabled',
            wrap='word',
            font=("Segoe UI", 10)
        )
        self.log_scroll = ttk.Scrollbar(self.root, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.log_scroll.set)
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("warning", foreground="orange")

        # Контейнер для прогрессбара с лейблом (лейбл ниже прогрессбара)
        self.progress_container = ttk.Frame(self.root)
        self.progress_bar = ttk.Progressbar(self.progress_container, mode="determinate", length=480)
        self.progress_bar.pack(fill='x')
        self.progress_label = tk.Label(self.progress_container, text="0%", anchor='center', font=("Segoe UI", 8, "bold"))
        self.progress_label.pack(pady=(2, 0))

        self.download_btn = ttk.Button(self.root, text="Download", command=self.start_download)
        self.help_btn = ttk.Button(self.root, text="?", width=3, command=self.show_help_info)

    def position_widgets(self):
        self.url_frame.grid(row=0, column=0, padx=10, pady=5, sticky='ew')
        self.help_btn.grid(row=0, column=2, padx=5, pady=5, sticky='e')
        self.url_label.pack(anchor='w', padx=5, pady=(5, 0))
        self.url_entry.pack(fill='x', padx=5, pady=(0, 5))

        self.path_frame.grid(row=1, column=0, padx=10, pady=5, sticky='ew', columnspan=2)
        self.path_label.pack(anchor='w', padx=5, pady=(5, 0))
        self.path_entry.pack(fill='x', padx=5, pady=(0, 5))
        self.path_btn.pack(pady=(0, 10))

        self.log_text.grid(row=2, column=0, padx=10, pady=10, sticky='nsew', columnspan=2)
        self.log_scroll.grid(row=2, column=2, padx=0, pady=10, sticky='ns')

        self.progress_container.grid(row=3, column=0, padx=10, pady=10, sticky='ew', columnspan=2)

        self.download_btn.config(width=20)
        self.download_btn.grid(row=4, column=0, padx=10, pady=10)
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
            "YouTube Downloader v0.5\n"
            "Author: stakan\n\n"
            "github.com/stakanyash"
        )
        messagebox.showinfo("About", help_text)

    def select_save_path(self):
        path = filedialog.askdirectory(title="Select Save Directory")
        if path:
            self.save_path = path
            self.path_entry.config(state='normal')
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)
            self.path_entry.config(state='readonly')

    def get_ffmpeg_location(self):
        self.log("Searching for ffmpeg...")
        try:
            ffmpeg_path = shutil.which('ffmpeg')
            if ffmpeg_path:
                self.log(f"Found in PATH: {ffmpeg_path}")
                return ffmpeg_path
        except Exception as e:
            self.log(f"PATH search error: {str(e)}")

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
            percent_str = d.get('_percent_str', '')
            if percent_str:
                try:
                    ansi_clean = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', percent_str)
                    cleaned_percent = re.sub(r'[^\d.]', '', ansi_clean).strip()
                    percent = float(cleaned_percent)

                    if percent > 0.0 and not getattr(self, '_progress_reported', False):
                        self.log("Download started...")
                        self._progress_reported = True

                    self.progress_bar['value'] = percent
                    self.progress_label.config(text=f"{percent:.1f}%")
                except Exception as e:
                    self.log(f"WARNING: Couldn't parse progress: {str(e)}")

        elif d['status'] == 'finished':
            if not getattr(self, '_merging_reported', False):
                self.log("Download finished. Merging...")
                self._merging_reported = True

            self.progress_bar['value'] = 100
            self.progress_label.config(text="100%")

    def _get_firefox_cookies_debug(self):
        self.log("Extracting cookies from Firefox...")
        try:
            cookies = browser_cookie3.firefox(domain_name="youtube.com")
            cookie_list = list(cookies)
            self.log(f"Successfully loaded {len(cookie_list)} YouTube-related cookies")
            return cookie_list
        except Exception as e:
            self.log(f"Error extracting Firefox cookies: {str(e)}")
            return []

    def download_video(self, url):
        try:
            self._progress_reported = False
            self._merging_reported = False
            self.progress_bar['value'] = 0
            self.progress_label.config(text="0%")
            self.ffmpeg_path = self.get_ffmpeg_location()

            firefox_cookies = self._get_firefox_cookies_debug()
            if not firefox_cookies:
                messagebox.showerror("Error", "Failed to load cookies from Firefox")
                return

            cookies_file = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
            self.write_cookies_to_file(firefox_cookies, cookies_file)

            ydl_opts = {
                'format': 'bestvideo[height<=1080][fps<=60]+bestaudio/best[height<=1080]',
                'outtmpl': os.path.join(self.save_path, '%(title)s.%(ext)s'),
                'progress_hooks': [self.progress_hook],
                'cookiefile': cookies_file,
                'noplaylist': True,
                'merge_output_format': 'mp4',
                'retries': 10,
                'fragment_retries': 10,
                'ffmpeg_location': self.ffmpeg_path,
                'postprocessor_args': ['-threads', '4'],
            }

            if not self.ffmpeg_path:
                self.log("Warning: FFmpeg not found - limited format support")

            self.log("Starting download process...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.log("Download completed successfully!")
            messagebox.showinfo("Success", "Download completed!")

            if os.path.exists(cookies_file):
                try:
                    os.remove(cookies_file)
                    self.log(f"Temporary cookies file {cookies_file} deleted.")
                except Exception as e:
                    self.log(f"Warning: Failed to delete cookies file: {e}")

        except Exception as e:
            error_msg = str(e)
            if "ffmpeg" in error_msg.lower():
                error_msg += "\nPlease install FFmpeg and add it to PATH or program directory"
            self.log(f"ERROR: {error_msg}")
            messagebox.showerror("Error", error_msg)

        finally:
            self.progress_bar['value'] = 0
            self.progress_label.config(text="0%")
            self._download_started = False

    def write_cookies_to_file(self, cookies, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("# Netscape HTTP Cookie File\n")
                for cookie in cookies:
                    domain = cookie.domain
                    flag = "TRUE" if domain.startswith('.') else "FALSE"
                    path = cookie.path
                    secure = "TRUE" if cookie.secure else "FALSE"
                    expires = str(cookie.expires) if cookie.expires else '0'
                    name = cookie.name
                    value = cookie.value
                    f.write("\t".join([
                        domain,
                        flag,
                        path,
                        secure,
                        expires,
                        name,
                        value
                    ]) + "\n")
            self.log(f"Cookies saved to {filename}")
        except Exception as e:
            self.log(f"Error saving cookies: {str(e)}")

    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Input Error", "Please enter a valid URL")
            return
        
        self.progress_bar['value'] = 0
        self.progress_label.config(text="0%")
        self._download_started = False

        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')

        thread = threading.Thread(target=self.download_video, args=(url,), daemon=True)
        thread.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()