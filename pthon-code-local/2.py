import instaloader
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import threading
import time
import secrets
import os
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# ------------------------------------------------------------
#  THE MAIN REBEL APP
# ------------------------------------------------------------
class GiveawayApp:
    def __init__(self, root):
        self.root = root
        root.title("IG Giveaway Picker - Navigator Edition")
        root.geometry("800x720")
        root.resizable(False, False)

        # ---- TOP FRAME: Connection Status ----
        self.status_frame = tk.LabelFrame(root, text="Connection Status", padx=10, pady=10)
        self.status_frame.grid(row=0, column=0, columnspan=3, sticky='we', padx=10, pady=5)

        self.conn_status_label = tk.Label(self.status_frame, text="🔴 NOT CONNECTED", fg="red", font=("Arial", 12, "bold"))
        self.conn_status_label.pack(side='left', padx=10)

        self.connect_btn = tk.Button(self.status_frame, text="🌐 Connect via Browser (Pop-up)", 
                                     command=self.start_browser_connect, bg="#FF5722", fg="white", padx=15)
        self.connect_btn.pack(side='left', padx=10)

        self.cookie_status_label = tk.Label(self.status_frame, text="📁 No cookie file", fg="gray")
        self.cookie_status_label.pack(side='left', padx=10)

        # ---- CREDENTIALS (fallback, but we will rely on cookies) ----
        tk.Label(root, text="Instagram Username (optional fallback):").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.username_entry = tk.Entry(root, width=30)
        self.username_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(root, text="Password (optional fallback):").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.password_entry = tk.Entry(root, width=30, show='*')
        self.password_entry.grid(row=2, column=1, padx=5, pady=5)

        # ---- POST URL ----
        tk.Label(root, text="Post URL:").grid(row=3, column=0, sticky='e', padx=5, pady=5)
        self.url_entry = tk.Entry(root, width=60)
        self.url_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5)

        # ---- FILTERS ----
        self.like_var = tk.IntVar(value=1)
        self.follow_var = tk.IntVar(value=1)
        tk.Checkbutton(root, text="Must have liked the post", variable=self.like_var).grid(row=4, column=0, columnspan=2, sticky='w', padx=20)
        tk.Checkbutton(root, text="Must follow the account", variable=self.follow_var).grid(row=5, column=0, columnspan=2, sticky='w', padx=20)

        tk.Label(root, text="Number of winners:").grid(row=6, column=0, sticky='e', padx=5, pady=5)
        self.num_winners_entry = tk.Entry(root, width=10)
        self.num_winners_entry.grid(row=6, column=1, sticky='w', padx=5, pady=5)
        self.num_winners_entry.insert(0, "1")

        # ---- BUTTONS ----
        self.start_btn = tk.Button(root, text="Start Harvesting", command=self.start_harvest, bg='#4CAF50', fg='white', state='disabled')
        self.start_btn.grid(row=7, column=0, pady=10)
        self.draw_btn = tk.Button(root, text="Pick Winners", command=self.pick_winners, bg='#2196F3', fg='white', state='disabled')
        self.draw_btn.grid(row=7, column=1, pady=10)
        self.checkpoint_btn = tk.Button(root, text="✓ I've completed the checkpoint (manual)", command=self.retry_after_checkpoint, bg='#FF9800', fg='white', state='disabled')
        self.checkpoint_btn.grid(row=7, column=2, pady=10)

        # ---- PROGRESS ----
        self.progress = ttk.Progressbar(root, orient='horizontal', length=700, mode='determinate')
        self.progress.grid(row=8, column=0, columnspan=3, pady=10)

        # ---- LOG ----
        self.log = scrolledtext.ScrolledText(root, width=90, height=22, state='normal')
        self.log.grid(row=9, column=0, columnspan=3, padx=10, pady=10)
        self.log.insert(tk.END, "🚀 Ready. Click 'Connect via Browser' to log in securely.\n")

        # ---- INTERNAL STATE ----
        self.eligible_users = []
        self.post = None
        self.loader = None
        self.target_profile = None
        self.is_connected = False
        self.cookie_file = "insta_cookies.json"

        # Check if cookie file exists on startup
        self.refresh_cookie_status()

    # ------------------------------------------------------------
    #  UI HELPERS
    # ------------------------------------------------------------
    def log_msg(self, msg):
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)

    def refresh_cookie_status(self):
        if os.path.exists(self.cookie_file):
            self.cookie_status_label.config(text=f"✅ Cookies loaded: {self.cookie_file}", fg="green")
            self.conn_status_label.config(text="🟢 COOKIES FOUND (Ready)", fg="green")
            self.start_btn.config(state='normal')
            self.is_connected = True
        else:
            self.cookie_status_label.config(text="❌ No cookie file found", fg="red")
            self.conn_status_label.config(text="🔴 NOT CONNECTED", fg="red")
            self.start_btn.config(state='disabled')
            self.is_connected = False

    # ------------------------------------------------------------
    #  THE "NAVIGATOR" POP-UP (SELENIUM)
    # ------------------------------------------------------------
    def start_browser_connect(self):
        self.connect_btn.config(state='disabled', text="⏳ Opening browser...")
        self.log_msg("🌐 Launching Chrome navigator window...")
        threading.Thread(target=self.browser_connect_thread, daemon=True).start()

    def browser_connect_thread(self):
        driver = None
        try:
            # Setup Chrome options
            chrome_options = Options()
            # We keep the window visible so the user can interact
            # chrome_options.add_argument("--headless")  # NOT headless!
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Auto-download and start ChromeDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Navigate to Instagram
            driver.get("https://www.instagram.com/")
            self.log_msg("📌 Instagram loaded in pop-up. Please log in manually (handle 2FA/checkpoint if needed).")
            self.root.after(0, lambda: self.connect_btn.config(text="⏳ Waiting for login..."))
            
            # Wait up to 180 seconds (3 minutes) for the user to log in
            # We detect login by the presence of the 'sessionid' cookie
            logged_in = False
            start_time = time.time()
            while time.time() - start_time < 180:
                try:
                    cookies = driver.get_cookies()
                    for cookie in cookies:
                        if cookie['name'] == 'sessionid':
                            logged_in = True
                            break
                    if logged_in:
                        break
                    time.sleep(2)
                    self.root.after(0, lambda: self.log_msg("⏳ Still waiting for you to log in..."))
                except:
                    time.sleep(1)
            
            if not logged_in:
                self.log_msg("❌ Timeout (180s) – you didn't log in. Please try again.")
                self.root.after(0, lambda: self.connect_btn.config(state='normal', text="🌐 Connect via Browser (Pop-up)"))
                if driver:
                    driver.quit()
                return

            # We are logged in! Save the cookies to the JSON file
            cookies = driver.get_cookies()
            with open(self.cookie_file, 'w') as f:
                json.dump(cookies, f, indent=2)
            
            self.log_msg(f"✅ SUCCESS! {len(cookies)} cookies saved to '{self.cookie_file}'")
            self.log_msg("🔒 Browser will close now. You can use this session for harvesting.")
            
            # Refresh UI status
            self.root.after(0, self.refresh_cookie_status)
            self.root.after(0, lambda: self.connect_btn.config(state='normal', text="🌐 Re-connect (Refresh Cookies)"))
            
            # Close the browser pop-up
            driver.quit()
            self.log_msg("🖥️ Browser pop-up closed.")

        except Exception as e:
            self.log_msg(f"💥 Browser connect error: {e}")
            if driver:
                driver.quit()
            self.root.after(0, lambda: self.connect_btn.config(state='normal', text="🌐 Connect via Browser (Pop-up)"))

    # ------------------------------------------------------------
    #  LOAD COOKIES INTO INSTALOADER
    # ------------------------------------------------------------
    def load_cookies_into_loader(self, loader):
        if not os.path.exists(self.cookie_file):
            return False
        try:
            with open(self.cookie_file, 'r') as f:
                cookies = json.load(f)
            for cookie in cookies:
                # Selenium cookies have 'domain', 'name', 'value', 'path', etc.
                # Instaloader uses requests.Session, which needs a cookie dict.
                # But we can directly set them in the session.
                if 'sameSite' in cookie:
                    del cookie['sameSite']  # requests doesn't like this key
                if 'expiry' in cookie:
                    # Convert expiry to int if it's not already
                    cookie['expires'] = cookie.pop('expiry')
                # Ensure domain is set correctly
                if 'domain' not in cookie:
                    cookie['domain'] = '.instagram.com'
                loader.context._session.cookies.set(cookie['name'], cookie['value'], 
                                                   domain=cookie['domain'], path=cookie.get('path', '/'))
            # Verify by trying to get the profile of the logged-in user
            # We can't know the username from cookies easily, but we can test.
            test_profile = instaloader.Profile.from_username(loader.context, self.username_entry.get().strip() or 'instagram')
            # If we got here, it's valid
            self.log_msg("✅ Cookies successfully injected into Instaloader session.")
            return True
        except Exception as e:
            self.log_msg(f"⚠️ Failed to load cookies into loader: {e}")
            return False

    # ------------------------------------------------------------
    #  RETRY AFTER MANUAL CHECKPOINT (legacy fallback)
    # ------------------------------------------------------------
    def retry_after_checkpoint(self):
        self.log_msg("🔄 Manual retry triggered...")
        self.checkpoint_btn.config(state='disabled')
        self.start_harvest()  # restart the harvest process

    # ------------------------------------------------------------
    #  MAIN HARVEST THREAD
    # ------------------------------------------------------------
    def start_harvest(self):
        if not self.is_connected and not os.path.exists(self.cookie_file):
            messagebox.showerror("Not Connected", "Please click 'Connect via Browser' first to log in and save cookies.")
            return
        self.start_btn.config(state='disabled')
        self.draw_btn.config(state='disabled')
        self.progress['value'] = 0
        threading.Thread(target=self.harvest_thread_func, daemon=True).start()

    def harvest_thread_func(self):
        try:
            username = self.username_entry.get().strip()
            password = self.password_entry.get().strip()
            url = self.url_entry.get().strip()
            if not url:
                self.log_msg("❌ Error: Post URL is required.")
                self.root.after(0, lambda: self.start_btn.config(state='normal'))
                return

            shortcode = re.search(r'/p/([^/]+)/', url)
            if not shortcode:
                self.log_msg("❌ Invalid post URL. Must contain /p/SHORTCODE/")
                self.root.after(0, lambda: self.start_btn.config(state='normal'))
                return
            shortcode = shortcode.group(1)

            # ---- INIT LOADER ----
            self.loader = instaloader.Instaloader(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            # ---- STRATEGY 1: LOAD FROM COOKIE FILE (The Navigator Way) ----
            cookie_loaded = False
            if os.path.exists(self.cookie_file):
                self.log_msg("🍪 Attempting to load session from saved cookies...")
                cookie_loaded = self.load_cookies_into_loader(self.loader)
                if cookie_loaded:
                    self.log_msg("✅ Session established via cookie file.")
            
            # ---- STRATEGY 2: LOAD FROM SESSION FILE (legacy) ----
            if not cookie_loaded:
                session_file = f"{username}_session.json"
                if os.path.exists(session_file):
                    try:
                        self.loader.load_session_from_file(username, session_file)
                        self.log_msg("✅ Session loaded from file.")
                        cookie_loaded = True
                    except Exception as e:
                        self.log_msg(f"⚠️ Session file invalid: {e}")

            # ---- STRATEGY 3: FALLBACK TO NORMAL LOGIN (risky) ----
            if not cookie_loaded and username and password:
                self.log_msg("🔐 Attempting regular login (will likely trigger checkpoint)...")
                try:
                    self.loader.login(username, password)
                    self.loader.save_session_to_file(session_file)
                    self.log_msg("✅ Login successful, session saved.")
                    cookie_loaded = True
                except instaloader.exceptions.CheckpointRequiredException as e:
                    err_msg = str(e)
                    match = re.search(r'(https?://[^\s]+)', err_msg)
                    if match:
                        checkpoint_url = match.group(0)
                        self.log_msg(f"🚨 CHECKPOINT REQUIRED! Open:\n{checkpoint_url}")
                        self.log_msg("✅ Complete verification, then click 'I've completed'.")
                        self.root.after(0, lambda: self.checkpoint_btn.config(state='normal'))
                        self.root.after(0, lambda: self.start_btn.config(state='normal'))
                        return
                    else:
                        self.log_msg(f"❌ Checkpoint error: {err_msg}")
                        self.root.after(0, lambda: self.start_btn.config(state='normal'))
                        return
                except Exception as e:
                    self.log_msg(f"❌ Login error: {e}")
                    self.root.after(0, lambda: self.start_btn.config(state='normal'))
                    return

            if not cookie_loaded:
                self.log_msg("❌ No valid authentication method succeeded. Use 'Connect via Browser'.")
                self.root.after(0, lambda: self.start_btn.config(state='normal'))
                return

            # ---- PROCEED WITH HARVEST ----
            self.root.after(0, lambda: self.checkpoint_btn.config(state='disabled'))

            self.log_msg(f"📥 Fetching post {shortcode}...")
            self.post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
            owner = self.post.owner_profile
            self.target_profile = owner
            self.log_msg(f"👤 Post by @{owner.username}")

            # 1. Comments
            self.log_msg("💬 Fetching ALL comments (including replies)...")
            commenters = set()
            total_comments = 0
            for comment in self.post.get_comments():
                commenters.add(comment.owner.username)
                total_comments += 1
                if comment.replies:
                    for reply in comment.replies:
                        commenters.add(reply.owner.username)
                        total_comments += 1
                if total_comments % 100 == 0:
                    self.root.after(0, lambda v=total_comments: self.progress.config(value=min(v/20, 30)))
            self.log_msg(f"✅ Found {len(commenters)} unique commenters from {total_comments} comments.")
            self.progress['value'] = 30

            # 2. Likers
            likers = set()
            if self.like_var.get() == 1:
                self.log_msg("❤️ Fetching likers...")
                for like in self.post.get_likes():
                    likers.add(like.username)
                    if len(likers) % 100 == 0:
                        self.root.after(0, lambda v=len(likers): self.progress.config(value=min(30 + v/30, 60)))
                self.log_msg(f"✅ Found {len(likers)} unique likers.")
            else:
                self.log_msg("⏭️ Skipping likers (filter disabled).")
            self.progress['value'] = 60

            # 3. Followers
            followers = set()
            if self.follow_var.get() == 1:
                self.log_msg(f"👥 Fetching followers of @{owner.username} (this may take a while)...")
                try:
                    for follower in owner.get_followers():
                        followers.add(follower.username)
                        if len(followers) % 200 == 0:
                            self.root.after(0, lambda v=len(followers): self.progress.config(value=min(60 + v/100, 90)))
                    self.log_msg(f"✅ Found {len(followers)} followers.")
                except Exception as e:
                    self.log_msg(f"⚠️ Followers fetch failed: {e}. Proceeding without follow filter.")
                    followers = set()
            else:
                self.log_msg("⏭️ Skipping followers (filter disabled).")
            self.progress['value'] = 90

            # 4. Filter
            self.log_msg("🔍 Filtering eligible users...")
            require_like = (self.like_var.get() == 1)
            require_follow = (self.follow_var.get() == 1)
            eligible = []
            for commenter in commenters:
                if require_like and commenter not in likers:
                    continue
                if require_follow and commenter not in followers:
                    continue
                eligible.append(commenter)
            self.eligible_users = list(set(eligible))
            self.log_msg(f"🎯 Eligible users count: {len(self.eligible_users)}")
            self.progress['value'] = 100

            self.root.after(0, lambda: self.draw_btn.config(state='normal'))
            self.root.after(0, lambda: self.start_btn.config(state='normal'))
            self.log_msg("✅ Harvest complete! Click 'Pick Winners'.")

        except Exception as e:
            self.log_msg(f"💥 FATAL ERROR: {e}")
            import traceback
            self.log_msg(traceback.format_exc())
            self.root.after(0, lambda: self.start_btn.config(state='normal'))
            self.root.after(0, lambda: self.draw_btn.config(state='normal'))

    # ------------------------------------------------------------
    #  PICK WINNERS
    # ------------------------------------------------------------
    def pick_winners(self):
        try:
            num = int(self.num_winners_entry.get().strip())
            if num <= 0:
                messagebox.showerror("Error", "Number must be > 0")
                return
            if len(self.eligible_users) == 0:
                messagebox.showwarning("No eligible", "No eligible users found.")
                return
            if len(self.eligible_users) < num:
                messagebox.showwarning("Not enough", f"Only {len(self.eligible_users)} eligible. Adjusting to that.")
                num = len(self.eligible_users)
            winners = secrets.sample(self.eligible_users, num)
            self.log_msg("\n🏆🏆🏆 WINNERS 🏆🏆🏆")
            for i, w in enumerate(winners, 1):
                self.log_msg(f"{i}. @{w}")
            self.log_msg("🏁 END OF LIST\n")
        except Exception as e:
            messagebox.showerror("Error", str(e))

# ------------------------------------------------------------
#  RUN THE APP
# ------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = GiveawayApp(root)
    root.mainloop()