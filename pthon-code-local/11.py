import sys
import random
import os
import json
import time
from urllib.parse import urlparse
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QMessageBox, QTabWidget,
    QSlider, QCheckBox
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QPalette, QColor

# ---- Instagrapi ----
from instagrapi import Client

# ---- Selenium for Edge ----
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# ================= CONFIG =================
SESSION_FILE = "session.json"          # instagrapi session (optional)
COOKIE_FILE = "insta_cookies.json"     # cookies from Edge
MAX_RETRIES = 3
RETRY_DELAY = 3
# ==========================================

class EdgeConnector(QThread):
    finished = Signal(bool)  # True if cookies saved
    log = Signal(str)

    def run(self):
        driver = None
        try:
            self.log.emit("🌐 Launching Edge navigator...")
            edge_options = EdgeOptions()
            edge_options.add_argument("--disable-blink-features=AutomationControlled")
            edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            edge_options.add_experimental_option('useAutomationExtension', False)
            # Use a random user‑agent
            ua = random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/118.0.0.0 Safari/537.36',
            ])
            edge_options.add_argument(f'user-agent={ua}')
            
            service = EdgeService(EdgeChromiumDriverManager().install())
            driver = webdriver.Edge(service=service, options=edge_options)
            driver.get("https://www.instagram.com/")
            self.log.emit("📌 Edge pop-up: please log in (handle 2FA/checkpoint if needed).")
            
            # Wait up to 180 seconds for sessionid cookie
            logged_in = False
            start = time.time()
            while time.time() - start < 180:
                try:
                    cookies = driver.get_cookies()
                    for c in cookies:
                        if c['name'] == 'sessionid':
                            logged_in = True
                            break
                    if logged_in:
                        break
                    time.sleep(2)
                except:
                    time.sleep(1)
            
            if not logged_in:
                self.log.emit("❌ Timeout (180s) – no login detected.")
                self.finished.emit(False)
                if driver: driver.quit()
                return

            # Save cookies
            cookies = driver.get_cookies()
            with open(COOKIE_FILE, 'w') as f:
                json.dump(cookies, f, indent=2)
            self.log.emit(f"✅ Saved {len(cookies)} cookies to {COOKIE_FILE}")
            driver.quit()
            self.log.emit("🖥️ Edge closed.")
            self.finished.emit(True)

        except Exception as e:
            self.log.emit(f"💥 Edge error: {e}")
            if driver: driver.quit()
            self.finished.emit(False)


class WorkerThread(QThread):
    finished = Signal(list)
    error = Signal(str)
    log = Signal(str)

    def __init__(self, username, url_or_id, delay=5, use_proxy=""):
        super().__init__()
        self.username = username.strip()
        self.url_or_id = url_or_id.strip()
        self.delay = delay
        self.proxy = use_proxy.strip()
        self.client = None

    def setup_client(self):
        """Create and configure instagrapi client with realistic settings."""
        cl = Client()
        cl.set_settings({
            'device_settings': {
                'android_version': '12',
                'android_release': '12',
                'dpi': '420dpi',
                'resolution': '1080x2220',
                'manufacturer': 'OnePlus',
                'device': 'OnePlus 9',
                'model': 'LE2115',
                'cpu': 'qcom',
                'gpu': 'adreno',
                'device_type': 'android',
                'timezone_offset': '7200',
            },
            'app_version': '258.0.0.18.118',
            'android_version': '12',
            'android_release': '12',
            'client_lang': 'en_US',
            'locale': 'en_US',
            'country': 'US',
            'country_code': 1,
            'timezone_offset': 7200
        })
        # Set delay range (random between delay/2 and delay*1.5)
        cl.delay_range = [self.delay * 0.5, self.delay * 1.5]
        if self.proxy:
            cl.set_proxy(self.proxy)
        return cl

    def load_cookies_from_edge(self, cl):
        """Load cookies from insta_cookies.json into the client."""
        if not os.path.exists(COOKIE_FILE):
            return False
        try:
            with open(COOKIE_FILE, 'r') as f:
                cookies = json.load(f)
            # Convert to format expected by instagrapi (list of dicts with 'name', 'value', etc.)
            cl.set_cookies(cookies)
            # Test by getting user_id (lightweight)
            cl.get_user_id(self.username)
            self.log.emit("✅ Cookies loaded and verified.")
            return True
        except Exception as e:
            self.log.emit(f"⚠️ Cookie load failed: {e}")
            return False

    def run(self):
        try:
            self.log.emit("🔧 Initialising client...")
            self.client = self.setup_client()

            # ---- Step 1: Load cookies from Edge ----
            if not self.load_cookies_from_edge(self.client):
                self.error.emit("❌ No valid cookies. Please click 'Connect via Edge' first.")
                return

            # ---- Step 2: Extract media ID ----
            media_id = None
            # If input is numeric, assume media ID
            if self.url_or_id.isdigit():
                media_id = int(self.url_or_id)
            else:
                # Try to get shortcode from URL
                parsed = urlparse(self.url_or_id)
                path = parsed.path.strip("/")
                if path.startswith("p/") or path.startswith("reel/") or path.startswith("tv/"):
                    shortcode = path.split("/")[1]
                    try:
                        media_id = self.client.media_id(shortcode)
                    except:
                        pass
                if not media_id:
                    try:
                        media_id = self.client.media_pk_from_url(self.url_or_id)
                    except:
                        pass

            if not media_id:
                self.error.emit("❌ Could not extract media ID. Provide a valid URL or numeric ID.")
                return

            # ---- Step 3: Fetch media info (with retries) ----
            media = None
            for attempt in range(MAX_RETRIES):
                try:
                    media = self.client.media_info(media_id)
                    if media:
                        break
                except Exception as e:
                    err = str(e).lower()
                    if "login required" in err:
                        self.error.emit("🔒 Login expired. Reconnect via Edge.")
                        return
                    elif "not found" in err or "media not found" in err:
                        if attempt == MAX_RETRIES - 1:
                            self.error.emit("🚫 Media not found or inaccessible.")
                            return
                    elif "private" in err:
                        self.error.emit("🔐 Account is private. You must follow it.")
                        return
                    time.sleep(RETRY_DELAY * (2 ** attempt))
            if not media:
                self.error.emit("🚫 Media not found.")
                return

            # ---- Step 4: Fetch comments (with retries) ----
            comments = None
            for attempt in range(MAX_RETRIES):
                try:
                    comments = self.client.media_comments(media_id, amount=500)
                    if comments is not None and len(comments) > 0:
                        break
                except Exception as e:
                    err = str(e).lower()
                    if "rate" in err or "retry" in err or "fail" in err:
                        time.sleep(RETRY_DELAY * (2 ** attempt))
                    elif "private" in err:
                        self.error.emit("🔐 Account is private.")
                        return
                    elif "not found" in err:
                        self.error.emit("🚫 Media not found.")
                        return
                    if attempt == MAX_RETRIES - 1:
                        self.error.emit(f"Failed to fetch comments: {str(e)}")
                        return

            if not comments:
                self.error.emit("📭 No comments found.")
                return

            # ---- Step 5: Deduplicate by user ----
            unique = {}
            for c in comments:
                uid = c.user.pk
                if uid not in unique:
                    unique[uid] = {
                        "username": c.user.username,
                        "full_name": c.user.full_name or "",
                        "text": c.text
                    }
            users = list(unique.values())
            if len(users) < 3:
                self.error.emit(f"⚠️ Not enough unique commenters: {len(users)} (need 3)")
                return

            winners = random.sample(users, 3)
            self.finished.emit(winners)

        except Exception as e:
            self.error.emit(f"Error: {str(e)}")


class WinnerCard(QWidget):
    def __init__(self, place, username, full_name=""):
        super().__init__()
        self.setFixedHeight(130)
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2c3e50, stop:1 #1a2530);
                border-radius: 16px;
                border: 2px solid #3498db;
                padding: 10px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(25, 15, 25, 15)

        medal = QLabel(place)
        medal.setFont(QFont("Segoe UI Emoji", 22, QFont.Bold))
        medal.setStyleSheet("color: white; margin-right: 10px;")

        info = QVBoxLayout()
        user_label = QLabel(f"@{username}")
        user_label.setFont(QFont("Segoe UI", 15, QFont.Bold))
        user_label.setStyleSheet("color: #f1c40f;")

        if full_name:
            name_label = QLabel(full_name)
            name_label.setFont(QFont("Segoe UI", 11))
            name_label.setStyleSheet("color: #bdc3c7;")
            info.addWidget(name_label)

        info.addWidget(user_label)
        layout.addWidget(medal, alignment=Qt.AlignVCenter)
        layout.addLayout(info)
        layout.addStretch()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎥 Winner Picker (Hybrid Edge+instagrapi)")
        self.setFixedSize(720, 920)
        self.setup_dark_theme()
        self.init_ui()

    def setup_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #121212;
                color: #e0e0e0;
            }
            QLabel { color: #ffffff; }
        """)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(20)
        layout.setContentsMargins(35, 35, 35, 35)

        title = QLabel("🎥 Winner Picker")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #00e676;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Connect via Edge, then enter URL/ID and pick winners")
        subtitle.setFont(QFont("Segoe UI", 11))
        subtitle.setStyleSheet("color: #80deea;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # ---- Connect via Edge button ----
        self.connect_btn = QPushButton("🌐 Connect via Edge (Get Cookies)")
        self.connect_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background: #FF5722;
                color: white;
                border-radius: 14px;
                padding: 12px;
            }
            QPushButton:hover { background: #E64A19; }
        """)
        self.connect_btn.clicked.connect(self.start_edge_connect)
        layout.addWidget(self.connect_btn)

        # ---- Connection status ----
        self.status_label = QLabel("🔴 Not connected")
        self.status_label.setStyleSheet("color: #ff5252; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # ---- Tabs for URL or ID ----
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabBar::tab { background: #2d2d2d; padding: 10px; border-radius: 8px; margin: 2px; }
            QTabBar::tab:selected { background: #00e676; }
        """)

        url_tab = QWidget()
        url_layout = QVBoxLayout(url_tab)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("🔗 Reel/Post URL (https://www.instagram.com/reel/...)")
        self.style_input(self.url_input)
        url_layout.addWidget(self.url_input)
        tabs.addTab(url_tab, "🌐 URL")

        id_tab = QWidget()
        id_layout = QVBoxLayout(id_tab)
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("🆔 Media ID (numeric)")
        self.style_input(self.id_input)
        id_layout.addWidget(self.id_input)
        tabs.addTab(id_tab, "🔢 ID")

        layout.addWidget(tabs)

        # ---- Username (still needed for context) ----
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("📱 Your Instagram username (for cookie verification)")
        self.style_input(self.username_input)
        layout.addWidget(self.username_input)

        # ---- Delay slider ----
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("⏱️ Request delay (sec):"))
        self.delay_slider = QSlider(Qt.Horizontal)
        self.delay_slider.setRange(2, 15)
        self.delay_slider.setValue(5)
        self.delay_slider.setTickInterval(1)
        self.delay_slider.setTickPosition(QSlider.TicksBelow)
        self.delay_label = QLabel("5")
        self.delay_slider.valueChanged.connect(lambda v: self.delay_label.setText(str(v)))
        delay_layout.addWidget(self.delay_slider)
        delay_layout.addWidget(self.delay_label)
        layout.addLayout(delay_layout)

        # ---- Proxy input (optional) ----
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("🔌 Proxy (optional, e.g., socks5://user:pass@ip:port)")
        self.style_input(self.proxy_input)
        layout.addWidget(self.proxy_input)

        # ---- Pick button ----
        self.pick_btn = QPushButton("🎯 PICK 3 WINNERS")
        self.pick_btn.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.pick_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00c853, stop:1 #64dd17);
                color: white;
                border-radius: 14px;
                padding: 14px;
            }
            QPushButton:hover { background: #00e676; }
        """)
        self.pick_btn.clicked.connect(self.start_picking)
        layout.addWidget(self.pick_btn)

        # ---- Winners title ----
        winners_title = QLabel("🌟 Winners")
        winners_title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        winners_title.setStyleSheet("color: #ff80ab;")
        winners_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(winners_title)

        # ---- Scroll area ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 10px; background: #1e1e1e; }
            QScrollBar::handle:vertical { background: #424242; border-radius: 5px; }
        """)

        self.winners_container = QWidget()
        self.winners_layout = QVBoxLayout(self.winners_container)
        self.winners_layout.setAlignment(Qt.AlignTop)
        self.winners_layout.setSpacing(18)
        self.winners_layout.setContentsMargins(0, 0, 0, 30)

        scroll.setWidget(self.winners_container)
        layout.addWidget(scroll, 1)

        self.clear_winners()

    def style_input(self, line_edit):
        line_edit.setStyleSheet("""
            QLineEdit {
                background-color: #263238;
                color: white;
                border: 2px solid #37474f;
                border-radius: 12px;
                padding: 14px;
            }
            QLineEdit:focus { border: 2px solid #00e676; }
        """)
        line_edit.setFont(QFont("Segoe UI", 11))

    def clear_winners(self):
        while self.winners_layout.count():
            child = self.winners_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        placeholder = QLabel("No winners yet.\n\nConnect via Edge, then enter URL/ID and click the button above.")
        placeholder.setObjectName("placeholder")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #78909C; font-size: 14px; font-style: italic;")
        self.winners_layout.addWidget(placeholder)

    # ---- Edge connection ----
    def start_edge_connect(self):
        self.connect_btn.setEnabled(False)
        self.status_label.setText("⏳ Connecting...")
        self.status_label.setStyleSheet("color: #ffb74d; font-weight: bold;")
        self.edge_thread = EdgeConnector()
        self.edge_thread.log.connect(self.status_label.setText)
        self.edge_thread.finished.connect(self.edge_connect_finished)
        self.edge_thread.start()

    def edge_connect_finished(self, success):
        self.connect_btn.setEnabled(True)
        if success:
            self.status_label.setText("✅ Connected! Cookies saved.")
            self.status_label.setStyleSheet("color: #69f0ae; font-weight: bold;")
        else:
            self.status_label.setText("❌ Connection failed. Check log and retry.")
            self.status_label.setStyleSheet("color: #ff5252; font-weight: bold;")

    # ---- Picking ----
    def start_picking(self):
        username = self.username_input.text().strip()
        if not username:
            self.show_error("Please enter your Instagram username.")
            return

        # Get input from current tab
        url_or_id = self.url_input.text().strip() or self.id_input.text().strip()
        if not url_or_id:
            self.show_error("Please enter a URL or Media ID.")
            return

        delay = self.delay_slider.value()
        proxy = self.proxy_input.text().strip()

        # Remove placeholder
        for i in reversed(range(self.winners_layout.count())):
            w = self.winners_layout.itemAt(i).widget()
            if w and w.objectName() == "placeholder":
                w.deleteLater()
                break

        # Show loading
        loading = QLabel("🔍 Fetching comments...")
        loading.setAlignment(Qt.AlignCenter)
        loading.setStyleSheet("color: #bbdefb; font-size: 16px;")
        self.winners_layout.addWidget(loading)

        self.worker = WorkerThread(username, url_or_id, delay, proxy)
        self.worker.finished.connect(self.show_winners)
        self.worker.error.connect(self.on_error)
        self.worker.log.connect(lambda msg: self.status_label.setText(msg))
        self.worker.start()

    def show_winners(self, winners):
        while self.winners_layout.count():
            child = self.winners_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        places = ["🥇 1st", "🥈 2nd", "🥉 3rd"]
        for i, w in enumerate(winners):
            card = WinnerCard(places[i], w["username"], w["full_name"])
            self.winners_layout.addWidget(card)

    def on_error(self, msg):
        while self.winners_layout.count():
            child = self.winners_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        error = QLabel(f"❌ {msg}")
        error.setAlignment(Qt.AlignCenter)
        error.setStyleSheet("color: #ef5350; font-size: 15px; font-weight: bold;")
        self.winners_layout.addWidget(error)

    def show_error(self, msg):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Error")
        dlg.setText(msg)
        dlg.setIcon(QMessageBox.Warning)
        dlg.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(35, 35, 35))
    palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(35, 35, 35))
    palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.Highlight, QColor(0, 140, 255))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())