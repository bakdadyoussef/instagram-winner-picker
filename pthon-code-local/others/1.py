import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
from instagrapi import Client
import random
import os
import json
import threading
import asyncio
from playwright.async_api import async_playwright, Browser, Page
import nest_asyncio

# Apply nest_asyncio to allow asyncio to run inside Tkinter's main loop
nest_asyncio.apply()

# ================= CONFIGURATION =================
SESSION_FILE = "session_browser.json"
# ================================================

class InstagramReelWinnerPicker:
    def __init__(self, root):
        self.root = root
        self.root.title("🎥 Reel Comment Picker (10 Winners)")
        self.root.geometry("800x600")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e1e")

        self.cl = Client()
        # We will NOT set default settings here; they will be loaded from browser session
        self.setup_gui()
        self.logged_in = False
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.try_auto_load_browser_session()

    def setup_gui(self):
        # Title
        title = tk.Label(self.root, text="🎥 Reel Comment Picker (10 Winners)", font=("Helvetica", 16, "bold"),
                         fg="#ff55aa", bg="#1e1e1e")
        title.pack(pady=20)

        # Input frame
        input_frame = tk.Frame(self.root, bg="#1e1e1e")
        input_frame.pack(pady=10)

        tk.Label(input_frame, text="Instagram Username (optional):", font=("Helvetica", 10), fg="white", bg="#1e1e1e").grid(row=0, column=0, sticky="w", padx=5)
        self.username_entry = tk.Entry(input_frame, width=30, font=("Helvetica", 10), bg="#333", fg="white", insertbackground="white")
        self.username_entry.grid(row=0, column=1, padx=5)
        # Username is not strictly needed for browser login, but kept for reference

        tk.Label(input_frame, text="Password (optional):", font=("Helvetica", 10), fg="white", bg="#1e1e1e").grid(row=1, column=0, sticky="w", padx=5)
        self.password_entry = tk.Entry(input_frame, width=30, show="*", font=("Helvetica", 10), bg="#333", fg="white", insertbackground="white")
        self.password_entry.grid(row=1, column=1, padx=5)
        # Password is optional because we use manual browser login; you can leave blank

        tk.Label(input_frame, text="Reel URL:", font=("Helvetica", 10), fg="white", bg="#1e1e1e").grid(row=2, column=0, sticky="w", padx=5)
        self.url_entry = tk.Entry(input_frame, width=30, font=("Helvetica", 10), bg="#333", fg="white")
        self.url_entry.grid(row=2, column=1, padx=5)

        # Buttons
        button_frame = tk.Frame(self.root, bg="#1e1e1e")
        button_frame.pack(pady=10)

        self.browser_login_btn = tk.Button(button_frame, text="🌐 Browser Login (Get Session)", 
                                           command=self.start_browser_login,
                                           bg="#ff8800", fg="white", font=("Helvetica", 10, "bold"), 
                                           width=20, relief="flat", padx=10)
        self.browser_login_btn.grid(row=0, column=0, padx=5)

        self.pick_btn = tk.Button(button_frame, text="🎯 Pick 10 Winners", 
                                  command=self.start_pick_winners,
                                  bg="#0066cc", fg="white", font=("Helvetica", 10, "bold"), 
                                  width=16, relief="flat", padx=10)
        self.pick_btn.grid(row=0, column=1, padx=5)
        self.pick_btn.config(state="disabled")

        # Output log
        tk.Label(self.root, text="Log Output:", font=("Helvetica", 12), fg="white", bg="#1e1e1e").pack(pady=5)
        self.output = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=20, width=90,
                                                bg="#2a2a2a", fg="#dcdcdc", font=("Consolas", 9), insertbackground="white")
        self.output.pack(padx=20, pady=10)

        self.log("💡 Press 'Browser Login' to open a Chromium window and log in manually.")
        self.log("   After login, the session will be saved and you can pick winners.")

    def log(self, message):
        self.output.insert(tk.END, message + "\n")
        self.output.see(tk.END)

    def try_auto_load_browser_session(self):
        """Try to load a previously saved browser session (cookies + settings)"""
        if os.path.exists(SESSION_FILE):
            try:
                self.log("🔄 Loading saved browser session...")
                with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                self.cl.load_settings(saved_settings)
                # Verify session by trying a lightweight API call (e.g., get user ID)
                # We'll just mark as logged in if no error
                self.logged_in = True
                self.pick_btn.config(state="normal")
                self.log("✅ Session loaded successfully! You can now pick winners.")
            except Exception as e:
                self.log(f"❌ Failed to load session: {e}")
                self.log("   Please perform a fresh browser login.")

    # ---------- BROWSER LOGIN ASYNC ----------
    def start_browser_login(self):
        """Launch the browser login flow in a separate thread"""
        self.browser_login_btn.config(state="disabled")
        threading.Thread(target=self.run_browser_login, daemon=True).start()

    def run_browser_login(self):
        """Wrapper to run asyncio in a thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.browser_login_async())
        self.root.after(0, lambda: self.browser_login_btn.config(state="normal"))

    async def browser_login_async(self):
        """Async Playwright: open browser, let user log in, then extract session"""
        self.log("🌐 Launching Chromium browser...")
        try:
            async with async_playwright() as p:
                # Launch headful browser (you can set headless=False for visibility)
                browser = await p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                # Go to Instagram login page
                await page.goto("https://www.instagram.com/accounts/login/")
                self.log("🔑 Please log in manually in the browser window.")
                self.log("   Complete any 2FA, challenge, or verification steps.")

                # Wait for the user to log in successfully (by detecting presence of the main feed or profile icon)
                # We'll wait for the URL to change to something other than login, or wait for a nav element.
                try:
                    await page.wait_for_selector("nav", timeout=300000)  # 5 minutes max
                except:
                    self.log("⏰ Timeout waiting for login. Did you log in?")
                    await browser.close()
                    return

                self.log("✅ Login detected! Extracting cookies and session...")

                # Get cookies in the format instagrapi expects
                cookies = await context.cookies()
                # Convert to instagrapi's settings format
                # instagrapi uses a 'cookies' dict in the settings with key 'cookie'
                # We also need to retrieve the session ID and other tokens.
                # We'll use the standard approach: get the 'sessionid' cookie and set the user agent.
                settings = {
                    "cookies": {},
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "device_settings": {
                        "android_version": "12",
                        "android_release": "12",
                        "dpi": "420dpi",
                        "resolution": "1080x2220",
                        "manufacturer": "OnePlus",
                        "device": "OnePlus 9",
                        "model": "LE2115",
                        "cpu": "qcom",
                        "gpu": "adreno",
                        "device_type": "android",
                        "timezone_offset": "7200",
                    },
                    "app_version": "258.0.0.18.118",
                    "android_version": "12",
                    "android_release": "12",
                    "client_lang": "en_US",
                    "locale": "en_US",
                    "country": "US",
                    "country_code": 1,
                    "timezone_offset": 7200
                }

                # Extract relevant cookies
                for cookie in cookies:
                    name = cookie.get('name')
                    value = cookie.get('value')
                    if name and value:
                        settings["cookies"][name] = value

                # Also try to get the sessionid specifically
                if 'sessionid' not in settings["cookies"]:
                    # Some cookies might have different names; we'll still use all
                    pass

                # Save the settings to file
                with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=4)

                self.log("💾 Session saved to " + SESSION_FILE)

                # Now load this session into the instagrapi client
                self.cl.load_settings(settings)
                self.logged_in = True
                self.root.after(0, lambda: self.pick_btn.config(state="normal"))
                self.log("✅ Browser session loaded successfully! You can now pick winners.")

                # Close browser
                await browser.close()
                self.log("🌐 Browser closed.")

        except Exception as e:
            self.log(f"❌ Browser login error: {e}")

    # ---------- PICK WINNERS ----------
    def start_pick_winners(self):
        threading.Thread(target=self.pick_10_winners, daemon=True).start()

    def pick_10_winners(self):
        if not self.logged_in:
            self.log("❌ Not logged in! Please login via Browser Login first.")
            return

        reel_url = self.url_entry.get().strip()
        if not reel_url:
            self.root.after(0, lambda: messagebox.showerror("Error", "Please enter a Reel URL!"))
            return

        self.log("🔗 Extracting Reel ID from URL...")
        try:
            media_id = self.cl.media_pk_from_url(reel_url)  # Works for reels too!
            self.log(f"✅ Reel ID: {media_id}")
        except Exception as e:
            self.log(f"❌ Failed to get Reel ID: {e}")
            return

        self.log("📥 Fetching comments from Reel (up to 500)...")
        try:
            comments = self.cl.media_comments(media_id, amount=500)
            self.log(f"✅ Fetched {len(comments)} comments")
        except Exception as e:
            self.log(f"❌ Failed to fetch comments: {e}")
            return

        # Deduplicate: one comment per user
        unique_comments = {}
        for comment in comments:
            user_id = comment.user.pk
            if user_id not in unique_comments:
                unique_comments[user_id] = {
                    "username": comment.user.username,
                    "text": comment.text,
                    "full_name": comment.user.full_name or ""
                }

        self.log(f"🎯 Found {len(unique_comments)} unique users after removing duplicates")

        commenters_list = list(unique_comments.values())

        # CHANGE: require at least 10 unique commenters
        if len(commenters_list) < 10:
            self.log("❌ Not enough unique commenters! Need at least 10.")
            self.root.after(0, lambda: messagebox.showwarning("Not Enough", f"Only {len(commenters_list)} users commented."))
            return

        # Pick 10 random unique winners
        winners = random.sample(commenters_list, 10)

        self.log("\n" + "="*50)
        self.log("🏆 10 RANDOM WINNERS (Reel)")
        self.log("="*50)
        for i, w in enumerate(winners, 1):
            suffix = ["st", "nd", "rd", "th"][i-1] if i <= 3 else "th"
            self.log(f"{i}{suffix}. 🎉 @{w['username']}")
            if w['full_name']:
                self.log(f"     👤 {w['full_name']}")
            self.log(f"     💬 \"{w['text']}\"")
        self.log("="*50)

        # Show popup with list of winners
        winner_list = "\n".join([f"{i+1}. @{w['username']}" for i, w in enumerate(winners)])
        self.root.after(0, lambda: messagebox.showinfo(
            "🎥 Reel Winners!",
            f"10 Winners:\n\n{winner_list}\n\nCheck the log for full details."
        ))

# =============== RUN APP ===============
if __name__ == "__main__":
    root = tk.Tk()
    app = InstagramReelWinnerPicker(root)
    root.mainloop()