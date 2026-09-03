# InstaWin – Self-hosted Instagram Giveaway Winner Picker

Fetches **real comments** from public Instagram posts/Reels and picks a fair random winner.

## Features

- Paste any public Instagram post or Reel URL
- Fetches real comments (best effort – Instagram limits anonymous access)
- Filters: min tagged friends, required hashtag/keyword, remove duplicates
- Live spinning animation + verification code
- Ready for Render free tier

## Important Limitations

- Instagram does **not** allow full public access to all comments. Large posts often return only a partial list.
- “Must follow” and “Must like” **cannot** be verified automatically. Always check the winner manually.
- The scraper may stop working if Instagram changes their internal GraphQL `doc_id`s (common every few weeks).

## Local Development

```bash
cd instagram-winner-picker-real
npm install
npm start
```

Open http://localhost:3000

## Deploy to Render (Free Tier)

1. Push this folder to a GitHub repository (or connect the folder).

2. Go to [https://dashboard.render.com](https://dashboard.render.com)

3. Click **New +** → **Web Service**

4. Connect your GitHub repo (or use the public URL if you uploaded it).

5. Settings:
   - **Name**: `instagram-winner-picker` (or anything)
   - **Runtime**: Node
   - **Build Command**: `npm install`
   - **Start Command**: `npm start`
   - **Instance Type**: Free

6. Click **Create Web Service**

7. Wait for the deploy to finish. Render will give you a URL like:  
   `https://instagram-winner-picker-xxxx.onrender.com`

### Free Tier Note
On the free plan the service **sleeps after 15 minutes** of no traffic.  
The first request after sleep can take 30–60 seconds while it wakes up. This is normal.

## Project Structure

```
instagram-winner-picker-real/
├── package.json
├── server.js          # Express backend + Instagram scraper
├── public/
│   └── index.html     # Frontend UI
└── README.md
```

## API

`POST /api/comments`  
Body: `{ "url": "https://www.instagram.com/p/XXXXX/" }`

Returns the list of comments found.
