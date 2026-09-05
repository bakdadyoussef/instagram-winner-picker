import instaloader
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import threading
import time
import random
import secrets
import os
import json

class GiveawayApp:
    def __init__(self, root):
        self.root = root
        root.title("IG Giveaway Winner Picker - Rebel Edition")
        root.geometry("700x600")
        root.resizable(False, False)

        # Credentials
        tk.Label(root, text="Instagram Username:").grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.username_entry = tk.Entry(root, width=30)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(root, text="Password:").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.password_entry = tk.Entry(root, width=30, show='*')
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        # Post URL
        tk.Label(root, text="Post URL:").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.url_entry = tk.Entry(root, width=60)
        self.url_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5)

        # Filters
        self.like_var = tk.IntVar(value=1)
        self.follow_var = tk.IntVar(value=1)
        tk.Checkbutton(root, text="Must have liked the post", variable=self.like_var).grid(row=3, column=0, columnspan=2, sticky='w', padx=20)
        tk.Checkbutton(root, text="Must follow the account", variable=self.follow_var).grid(row=4, column=0, columnspan=2, sticky='w', padx=20)

        # Number of winners
        tk.Label(root, text="Number of winners:").grid(row=5, column=0, sticky='e', padx=5, pady=5)
        self.num_winners_entry = tk.Entry(root, width=10)
        self.num_winners_entry.grid(row=5, column=1, sticky='w', padx=5, pady=5)
        self.num_winners_entry.insert(0, "1")

        # Buttons
        self.start_btn = tk.Button(root, text="Start Harvesting", command=self.start_harvest, bg='#4CAF50', fg='white')
        self.start_btn.grid(row=6, column=0, pady=10)
        self.draw_btn = tk.Button(root, text="Pick Winners", command=self.pick_winners, bg='#2196F3', fg='white', state='disabled')
        self.draw_btn.grid(row=6, column=1, pady=10)

        # Progress bar
        self.progress = ttk.Progressbar(root, orient='horizontal', length=400, mode='determinate')
        self.progress.grid(row=7, column=0, columnspan=3, pady=10)

        # Log area
        self.log = scrolledtext.ScrolledText(root, width=80, height=20, state='normal')
        self.log.grid(row=8, column=0, columnspan=3, padx=10, pady=10)
        self.log.insert(tk.END, "Ready. Enter credentials and post URL.\n")

        # Internal state
        self.eligible_users = []
        self.post = None
        self.loader = None
        self.target_profile = None

    def log_msg(self, msg):
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)

    def start_harvest(self):
        # Disable button during harvest
        self.start_btn.config(state='disabled')
        self.draw_btn.config(state='disabled')
        self.progress['value'] = 0
        threading.Thread(target=self.harvest_thread, daemon=True).start()

    def harvest_thread(self):
        try:
            username = self.username_entry.get().strip()
            password = self.password_entry.get().strip()
            url = self.url_entry.get().strip()
            if not username or not password or not url:
                self.log_msg("Error: All fields required.")
                self.root.after(0, lambda: self.start_btn.config(state='normal'))
                return

            # Extract shortcode
            import re
            match = re.search(r'/p/([^/]+)/', url)
            if not match:
                self.log_msg("Invalid post URL. Must contain /p/SHORTCODE/")
                self.root.after(0, lambda: self.start_btn.config(state='normal'))
                return
            shortcode = match.group(1)

            # Login
            self.log_msg("Logging in...")
            self.loader = instaloader.Instaloader(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            # Load session if exists
            session_file = f"{username}_session.json"
            if os.path.exists(session_file):
                try:
                    self.loader.load_session_from_file(username, session_file)
                    self.log_msg("Session loaded.")
                except:
                    pass
            if not self.loader.context.is_logged_in:
                self.loader.login(username, password)
                self.loader.save_session_to_file(session_file)
                self.log_msg("Login successful, session saved.")

            # Get post
            self.log_msg(f"Fetching post {shortcode}...")
            self.post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
            owner = self.post.owner_profile
            self.target_profile = owner
            self.log_msg(f"Post by @{owner.username}")

            # Step 1: Fetch all commenters
            self.log_msg("Fetching all comments (this may take a while)...")
            commenters = set()
            total_comments = 0
            for comment in self.post.get_comments():
                commenters.add(comment.owner.username)
                total_comments += 1
                # also replies
                if comment.replies:
                    for reply in comment.replies:
                        commenters.add(reply.owner.username)
                        total_comments += 1
                # update progress roughly (assuming 1000 comments max)
                if total_comments % 50 == 0:
                    self.root.after(0, lambda v=total_comments: self.progress.config(value=min(v/10, 50)))
            self.log_msg(f"Found {len(commenters)} unique commenters from {total_comments} comments.")
            self.progress['value'] = 50

            # Step 2: Fetch likers (if required)
            likers = set()
            if self.like_var.get() == 1:
                self.log_msg("Fetching all likers...")
                for like in self.post.get_likes():
                    likers.add(like.username)
                    if len(likers) % 100 == 0:
                        self.root.after(0, lambda v=len(likers): self.progress.config(value=min(50 + v/20, 75)))
                self.log_msg(f"Found {len(likers)} unique likers.")
            else:
                self.log_msg("Skipping likers (filter disabled).")
            self.progress['value'] = 75

            # Step 3: Fetch followers of the target account (if required)
            followers = set()
            if self.follow_var.get() == 1:
                self.log_msg(f"Fetching followers of @{owner.username} (this can be very slow for large accounts)...")
                try:
                    for follower in owner.get_followers():
                        followers.add(follower.username)
                        if len(followers) % 200 == 0:
                            self.root.after(0, lambda v=len(followers): self.progress.config(value=min(75 + v/100, 95)))
                    self.log_msg(f"Found {len(followers)} followers.")
                except Exception as e:
                    self.log_msg(f"Error fetching followers: {e}. Proceeding without follow filter.")
                    followers = set()  # empty means no filter
            else:
                self.log_msg("Skipping followers (filter disabled).")
            self.progress['value'] = 95

            # Step 4: Filter
            self.log_msg("Filtering eligible users...")
            eligible = []
            require_like = (self.like_var.get() == 1)
            require_follow = (self.follow_var.get() == 1)
            for commenter in commenters:
                if require_like and commenter not in likers:
                    continue
                if require_follow and commenter not in followers:
                    continue
                eligible.append(commenter)
            self.eligible_users = list(set(eligible))
            self.log_msg(f"Eligible users: {len(self.eligible_users)}")
            self.progress['value'] = 100

            # Enable draw button
            self.root.after(0, lambda: self.draw_btn.config(state='normal'))
            self.root.after(0, lambda: self.start_btn.config(state='normal'))
            self.log_msg("Harvest complete. Click 'Pick Winners'.")

        except Exception as e:
            self.log_msg(f"ERROR: {e}")
            self.root.after(0, lambda: self.start_btn.config(state='normal'))
            self.root.after(0, lambda: self.draw_btn.config(state='normal'))

    def pick_winners(self):
        try:
            num = int(self.num_winners_entry.get().strip())
            if num <= 0:
                messagebox.showerror("Error", "Number of winners must be > 0.")
                return
            if len(self.eligible_users) == 0:
                messagebox.showwarning("No eligible", "No eligible users found. Did you harvest?")
                return
            if len(self.eligible_users) < num:
                messagebox.showwarning("Not enough", f"Only {len(self.eligible_users)} eligible users, but you asked for {num}. Adjusting to {len(self.eligible_users)}.")
                num = len(self.eligible_users)
            winners = secrets.sample(self.eligible_users, num)
            self.log_msg("\n--- WINNERS ---")
            for i, w in enumerate(winners, 1):
                self.log_msg(f"{i}. @{w}")
            self.log_msg("--- END ---")
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = GiveawayApp(root)
    root.mainloop()