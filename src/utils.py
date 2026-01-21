import re
import os
import shutil
import platform

def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

class AppContext:
    ffmpeg_path = None
    
    @staticmethod
    def find_ffmpeg():
        # Сначала проверяем PATH
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
        
        system = platform.system()
        
        if system == "Windows":
            # Windows-специфичные пути
            common_paths = [
                "C:\\ffmpeg\\bin\\ffmpeg.exe",
                "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
                "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe"
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    return path
            
            # Проверяем Windows Registry
            try:
                import winreg
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\ffmpeg.exe"
                ) as key:
                    reg_path, _ = winreg.QueryValueEx(key, "")
                    if os.path.exists(reg_path):
                        return reg_path
            except ImportError:
                pass  # winreg не доступен на Linux
            except:
                pass
        
        elif system == "Linux":
            # Linux-специфичные пути
            common_paths = [
                "/usr/bin/ffmpeg",
                "/usr/local/bin/ffmpeg",
                "/snap/bin/ffmpeg",
                os.path.expanduser("~/bin/ffmpeg"),
                "/opt/ffmpeg/bin/ffmpeg"
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    return path
        
        elif system == "Darwin":  # macOS
            common_paths = [
                "/usr/local/bin/ffmpeg",
                "/opt/homebrew/bin/ffmpeg",
                "/usr/bin/ffmpeg"
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    return path
        
        return None