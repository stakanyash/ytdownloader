import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from ui import YouTubeDownloader


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeDownloader()
    window.show()
    
    QTimer.singleShot(100, window.init_ffmpeg)
    
    sys.exit(app.exec_())