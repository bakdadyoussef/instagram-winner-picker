import instaloader
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, Scale, IntVar, Entry
import threading
import time
import secrets
import os
import re
import json
import random
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# ------------------------------------------------------------
#  CONFIG
# ------------------------------------------------------------
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/118.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Edge/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
]
FOLLOWER_CACHE_TTL = 3600  # 1 hour

# ------------------------------------------------------------
#  THE MAIN APP
# ------------------------------------------------------------
class GiveawayApp:
    def __init__(self, root):
        self.root = root
        root.title("IG Giveaway Picker - FINAL v3 (fixed attr)")
        root.geometry("900x820")
        root.resizable(False, False)

        # ---- STATUS FRAME ----
        self.status_frame = tk.LabelFrame(root, text="Connection Status", padx=10, pady=10)
        self.status_frame.grid(row=0, column=0, columnspan=5, sticky='we', padx=10, pady=5)

        self.conn_status_label = tk.Label(self.status_frame, text="🔴 NOT CONNECTED", fg="red", font=("Arial", 12, "bold"))
        self.conn_status_label.pack(side='left', padx=10)

        self.connect_btn = tk.Button(self.status_frame, text="🌐 Connect via Edge", 
                                     command=self.start_browser_connect, bg="#FF5722", fg="white", padx=15)
        self.connect_btn.pack(side='left', padx=10)

        self.cookie_status_label = tk.Label(self.status_frame, text="📁 No cookie file", fg="gray")
        self.cookie_status_label.pack(side='left', padx=10)

        # ---- CREDENTIALS ----
        tk.Label(root, text="Instagram Username (required):").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.username_entry = Entry(root, width=30)
        self.username_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(root, text="Password (NOT USED - keep empty):").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.password_entry = Entry(root, width=30, show='*')
        self.password_entry.grid(row=2, column=1, padx=5, pady=5)
        self.password_entry.insert(0, "LEAVE EMPTY")

        # ---- POST URL ----
        tk.Label(root, text="Post URL:").grid(row=3, column=0, sticky='e', padx=5, pady=5)
        self.url_entry = Entry(root, width=60)
        self.url_entry.grid(row=3, column=1, columnspan=4, padx=5, pady=5)

        # ---- FILTERS ----
        self.like_var = IntVar(value=1)
        self.follow_var = IntVar(value=1)
        tk.Checkbutton(root, text="Must have liked the post", variable=self.like_var).grid(row=4, column=0, columnspan=2, sticky='w', padx=20)
        tk.Checkbutton(root, text="Must follow the account", variable=self.follow_var).grid(row=5, column=0, columnspan=2, sticky='w', padx=20)

        self.skip_followers_var = IntVar(value=0)
        tk.Checkbutton(root, text="Skip followers fetch entirely (saves requests)", variable=self.skip_followers_var, fg="blue").grid(row=6, column=0, columnspan=3, sticky='w', padx=20)

        # ---- WINNER COUNT ----
        tk.Label(root, text="Number of winners:").grid(row=7, column=0, sticky='e', padx=5, pady=5)
        self.num_winners_entry = Entry(root, width=10)
        self.num_winners_entry.grid(row=7, column=1, sticky='w', padx=5, pady=5)
        self.num_winners_entry.insert(0, "1")

        # ---- DELAY SLIDER ----
        tk.Label(root, text="Request delay (seconds):").grid(row=7, column=2, sticky='e', padx=5, pady=5)
        self.delay_slider = Scale(root, from_=2, to=15, orient='horizontal', length=150)
        self.delay_slider.set(5)
        self.delay_slider.grid(row=7, column=3, sticky='w', padx=5, pady=5)

        # ---- PROXY ENTRY ----
        tk.Label(root, text="Proxy (optional):").grid(row=8, column=0, sticky='e', padx=5, pady=5)
        self.proxy_entry = Entry(root, width=60)
        self.proxy_entry.grid(row=8, column=1, columnspan=4, padx=5, pady=5)

        # ---- BUTTONS ----
        self.start_btn = tk.Button(root, text="Start Harvesting", command=self.start_harvest, bg='#4CAF50', fg='white', state='disabled')
        self.start_btn.grid(row=9, column=0, pady=10)
        self.draw_btn = tk.Button(root, text="Pick Winners", command=self.pick_winners, bg='#2196F3', fg='white', state='disabled')
        self.draw_btn.grid(row=9, column=1, pady=10)
        self.checkpoint_btn = tk.Button(root, text="✓ I've completed checkpoint", command=self.retry_after_checkpoint, bg='#FF9800', fg='white', state='disabled')
        self.checkpoint_btn.grid(row=9, column=2, pady=10)

        # ---- PROGRESS ----
        self.progress = ttk.Progressbar(root, orient='horizontal', length=700, mode='determinate')
        self.progress.grid(row=10, column=0, columnspan=5, pady=10)

        # ---- LOG ----
        self.log = scrolledtext.ScrolledText(root, width=100, height=22, state='normal')
        self.log.grid(row=11, column=0, columnspan=5, padx=10, pady=10)
        self.log.insert(tk.END, "🚀 FINAL v3: All known bugs squashed.\n")

        # ---- STATE ----
        self.eligible_users = []
        self.post = None
        self.loader = None
        self.target_profile = None
        self.is_connected = False
        self.cookie_file = "insta_cookies.json"
        self.pending_checkpoint_url = None
        self.refresh_cookie_status()

    # ------------------------------------------------------------
    #  UI HELPERS
    # ------------------------------------------------------------
    def log_msg(self, msg):
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)

    def refresh_cookie_status(self):
        if os.path.exists(self.cookie_file):
            self.cookie_status_label.config(text=f"✅ Cookies: {self.cookie_file}", fg="green")
            self.conn_status_label.config(text="🟢 COOKIES FOUND", fg="green")
            self.start_btn.config(state='normal')
            self.is_connected = True
        else:
            self.cookie_status_label.config(text="❌ No cookie file", fg="red")
            self.conn_status_label.config(text="🔴 NOT CONNECTED", fg="red")
            self.start_btn.config(state='disabled')
            self.is_connected = False

    # ------------------------------------------------------------
    #  EDGE NAVIGATOR
    # ------------------------------------------------------------
    def start_browser_connect(self):
        self.connect_btn.config(state='disabled', text="⏳ Opening Edge...")
        self.log_msg("🌐 Launching Edge navigator...")
        threading.Thread(target=self.browser_connect_thread, daemon=True).start()

    def browser_connect_thread(self):
        driver = None
        try:
            edge_options = EdgeOptions()
            edge_options.add_argument("--disable-blink-features=AutomationControlled")
            edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            edge_options.add_experimental_option('useAutomationExtension', False)
            ua = random.choice(USER_AGENTS)
            edge_options.add_argument(f'user-agent={ua}')
            
            service = EdgeService(EdgeChromiumDriverManager().install())
            driver = webdriver.Edge(service=service, options=edge_options)
            driver.get("https://www.instagram.com/")
            self.log_msg("📌 Edge pop-up: please log in (handle 2FA/checkpoint).")
            self.root.after(0, lambda: self.connect_btn.config(text="⏳ Waiting for login..."))
            
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
                except:
                    time.sleep(1)
            
            if not logged_in:
                self.log_msg("❌ Timeout (180s). Try again.")
                self.root.after(0, lambda: self.connect_btn.config(state='normal', text="🌐 Connect via Edge"))
                if driver: driver.quit()
                return

            cookies = driver.get_cookies()
            with open(self.cookie_file, 'w') as f:
                json.dump(cookies, f, indent=2)
            self.log_msg(f"✅ Saved {len(cookies)} cookies to {self.cookie_file}")
            self.root.after(0, self.refresh_cookie_status)
            self.root.after(0, lambda: self.connect_btn.config(state='normal', text="🌐 Re-connect"))
            driver.quit()
            self.log_msg("🖥️ Edge closed.")

        except Exception as e:
            self.log_msg(f"💥 Edge error: {e}")
            if driver: driver.quit()
            self.root.after(0, lambda: self.connect_btn.config(state='normal', text="🌐 Connect via Edge"))

    # ------------------------------------------------------------
    #  LOAD COOKIES – FIXED
    # ------------------------------------------------------------
    def load_cookies_into_loader(self, loader, username):
        if not os.path.exists(self.cookie_file):
            return False
        try:
            with open(self.cookie_file, 'r') as f:
                cookies = json.load(f)
            
            cookie_dict = {}
            for cookie in cookies:
                cookie_dict[cookie['name']] = cookie['value']
            
            loader.context._session.cookies.update(cookie_dict)
            
            if 'csrftoken' in cookie_dict:
                loader.context._session.headers.update({'X-CSRFToken': cookie_dict['csrftoken']})
            
            loader.context.username = username
            
            # FIXED: use loader.context.user_agent
            user_agent = getattr(loader.context, 'user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36')
            loader.context._session.headers.update({'User-Agent': user_agent})
            
            if not loader.test_login():
                self.log_msg("⚠️ Cookie session is invalid (test_login failed).")
                return False
            
            self.log_msg(f"✅ Cookies injected and verified for @{username}")
            return True
        except Exception as e:
            self.log_msg(f"⚠️ Cookie loading error: {e}")
            return False

    # ------------------------------------------------------------
    #  RETRY CHECKPOINT
    # ------------------------------------------------------------
    def retry_after_checkpoint(self):
        self.log_msg("🔄 Manual retry triggered...")
        self.checkpoint_btn.config(state='disabled')
        self.start_harvest()

    # ------------------------------------------------------------
    #  MAIN HARVEST
    # ------------------------------------------------------------
    def start_harvest(self):
        if not self.is_connected and not os.path.exists(self.cookie_file):
            messagebox.showerror("Not Connected", "Please connect via Edge first.")
            return
        if not self.username_entry.get().strip():
            messagebox.showerror("Username required", "Please enter your Instagram username.")
            return
        self.start_btn.config(state='disabled')
        self.draw_btn.config(state='disabled')
        self.progress['value'] = 0
        threading.Thread(target=self.harvest_thread_func, daemon=True).start()

    def harvest_thread_func(self):
        max_retries = 5
        retry_delay = 600
        for attempt in range(max_retries):
            try:
                self._do_harvest()
                return
            except instaloader.exceptions.InstaloaderException as e:
                if '429' in str(e) or 'Too Many Requests' in str(e):
                    self.log_msg(f"🚨 429 detected. Cooldown for {retry_delay}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(retry_delay)
                    continue
                elif 'Checkpoint' in str(e) or 'checkpoint' in str(e):
                    match = re.search(r'(https?://[^\s]+)', str(e))
                    if match:
                        self.pending_checkpoint_url = match.group(0)
                        self.log_msg(f"🚨 CHECKPOINT REQUIRED! Open:\n{self.pending_checkpoint_url}")
                        self.log_msg("Complete verification, then click 'I've completed'.")
                        self.root.after(0, lambda: self.checkpoint_btn.config(state='normal'))
                        self.root.after(0, lambda: self.start_btn.config(state='normal'))
                    else:
                        self.log_msg(f"❌ Checkpoint error without URL: {e}")
                    return
                else:
                    self.log_msg(f"❌ Fatal error: {e}")
                    raise
            except Exception as e:
                self.log_msg(f"💥 Unexpected error: {e}")
                raise
        self.log_msg("❌ All retries failed.")
        self.root.after(0, lambda: self.start_btn.config(state='normal'))

    def _do_harvest(self):
        username = self.username_entry.get().strip()
        url = self.url_entry.get().strip()
        if not url:
            self.log_msg("❌ Post URL required.")
            self.root.after(0, lambda: self.start_btn.config(state='normal'))
            return

        shortcode = re.search(r'/p/([^/]+)/', url)
        if not shortcode:
            self.log_msg("❌ Invalid URL.")
            self.root.after(0, lambda: self.start_btn.config(state='normal'))
            return
        shortcode = shortcode.group(1)

        delay = float(self.delay_slider.get())
        if delay < 2:
            delay = 2
        ua = random.choice(USER_AGENTS)

        self.loader = instaloader.Instaloader(user_agent=ua)
        self.loader.request_delay = delay

        proxy_str = self.proxy_entry.get().strip()
        if proxy_str:
            proxies = {'http': proxy_str, 'https': proxy_str}
            self.loader.context._session.proxies.update(proxies)
            self.log_msg(f"🔀 Using proxy: {proxy_str.split('@')[-1] if '@' in proxy_str else proxy_str}")

        # ---- AUTHENTICATION: ONLY COOKIES ----
        if os.path.exists(self.cookie_file):
            self.log_msg("🍪 Loading cookies...")
            if not self.load_cookies_into_loader(self.loader, username):
                self.log_msg("⚠️ Cookie session invalid. Re-connect via Edge.")
                self.root.after(0, lambda: self.start_btn.config(state='normal'))
                return
        else:
            self.log_msg("❌ No cookie file. Click 'Connect via Edge' first.")
            self.root.after(0, lambda: self.start_btn.config(state='normal'))
            return

        self.root.after(0, lambda: self.checkpoint_btn.config(state='disabled'))

        # ---- FETCH POST ----
        self.log_msg(f"📥 Fetching post {shortcode}...")
        self.post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
        owner_username = self.post.owner_username
        self.log_msg(f"👤 Post by @{owner_username}")

        # ---- COMMENTS ----
        self.log_msg("💬 Fetching comments...")
        commenters = set()
        total_comments = 0
        for comment in self.post.get_comments():
            commenters.add(comment.owner.username)
            total_comments += 1
            if comment.replies:
                for reply in comment.replies:
                    commenters.add(reply.owner.username)
                    total_comments += 1
            if total_comments % 50 == 0:
                time.sleep(random.uniform(0.5, 1.5))
                self.root.after(0, lambda v=total_comments: self.progress.config(value=min(v/20, 30)))
        self.log_msg(f"✅ {len(commenters)} unique commenters.")
        self.progress['value'] = 30

        # ---- LIKERS ----
        likers = set()
        if self.like_var.get() == 1:
            self.log_msg("❤️ Fetching likers...")
            for like in self.post.get_likes():
                likers.add(like.username)
                if len(likers) % 100 == 0:
                    time.sleep(random.uniform(0.3, 1.0))
                    self.root.after(0, lambda v=len(likers): self.progress.config(value=min(30 + v/30, 60)))
            self.log_msg(f"✅ {len(likers)} likers.")
        else:
            self.log_msg("⏭️ Skipping likers.")
        self.progress['value'] = 60

        # ---- FOLLOWERS ----
        followers = set()
        skip_followers = (self.skip_followers_var.get() == 1)
        if self.follow_var.get() == 1 and not skip_followers:
            self.log_msg(f"👥 Fetching followers of @{owner_username}...")
            try:
                profile = instaloader.Profile.from_username(self.loader.context, owner_username)
            except Exception as e:
                self.log_msg(f"⚠️ Failed to get profile: {e}")
                profile = None
            if profile:
                cache_file = f"followers_cache_{owner_username}.json"
                if os.path.exists(cache_file):
                    mtime = os.path.getmtime(cache_file)
                    if time.time() - mtime < FOLLOWER_CACHE_TTL:
                        try:
                            with open(cache_file, 'r') as f:
                                followers = set(json.load(f))
                            self.log_msg(f"✅ Loaded {len(followers)} followers from cache.")
                        except:
                            pass
                if not followers:
                    try:
                        for follower in profile.get_followers():
                            followers.add(follower.username)
                            if len(followers) % 200 == 0:
                                time.sleep(random.uniform(1, 3))
                                self.root.after(0, lambda v=len(followers): self.progress.config(value=min(60 + v/100, 90)))
                        with open(cache_file, 'w') as f:
                            json.dump(list(followers), f)
                        self.log_msg(f"✅ Fetched {len(followers)} followers (cached).")
                    except Exception as e:
                        self.log_msg(f"⚠️ Followers fetch error: {e}")
                        followers = set()
            else:
                followers = set()
        else:
            if skip_followers:
                self.log_msg("⏭️ Skipping followers (user opted out).")
            else:
                self.log_msg("⏭️ Follow filter disabled.")
        self.progress['value'] = 90

        # ---- FILTER ----
        self.log_msg("🔍 Filtering...")
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
        self.log_msg(f"🎯 Eligible: {len(self.eligible_users)}")
        self.progress['value'] = 100

        self.root.after(0, lambda: self.draw_btn.config(state='normal'))
        self.root.after(0, lambda: self.start_btn.config(state='normal'))
        self.log_msg("✅ Harvest complete! Click 'Pick Winners'.")

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
                messagebox.showwarning("Not enough", f"Only {len(self.eligible_users)} eligible. Adjusting.")
                num = len(self.eligible_users)
            winners = secrets.sample(self.eligible_users, num)
            self.log_msg("\n🏆🏆🏆 WINNERS 🏆🏆🏆")
            for i, w in enumerate(winners, 1):
                self.log_msg(f"{i}. @{w}")
            self.log_msg("🏁 END\n")
        except Exception as e:
            messagebox.showerror("Error", str(e))

# ------------------------------------------------------------
#  RUN
# ------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = GiveawayApp(root)
    root.mainloop()