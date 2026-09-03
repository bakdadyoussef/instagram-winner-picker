const express = require('express');
const cors = require('cors');
const path = require('path');
const fetch = require('node-fetch');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ========== Instagram Comment Scraper ==========
// Uses public GraphQL endpoints (no login required)
// Note: Instagram rotates doc_ids periodically. If it stops working, update them.

const DOC_ID_COMMENTS = '26248690958161038'; // PolarisPostCommentsPaginationQuery (may need update)
const DOC_ID_CHILD = '26914912424764761';   // PolarisPostChildCommentsQuery

function extractShortcode(url) {
  try {
    const u = new URL(url);
    const parts = u.pathname.split('/').filter(Boolean);
    // /p/SHORTCODE/ or /reel/SHORTCODE/
    const idx = parts.findIndex(p => p === 'p' || p === 'reel' || p === 'tv');
    if (idx !== -1 && parts[idx + 1]) {
      return parts[idx + 1];
    }
    // fallback: last segment that looks like a shortcode
    return parts[parts.length - 1] || null;
  } catch {
    return null;
  }
}

async function fetchPostPage(shortcode) {
  const url = `https://www.instagram.com/p/${shortcode}/`;
  const res = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Sec-Fetch-Dest': 'document',
      'Sec-Fetch-Mode': 'navigate',
      'Sec-Fetch-Site': 'none',
      'Upgrade-Insecure-Requests': '1',
    },
    timeout: 15000,
  });

  if (!res.ok) {
    throw new Error(`Failed to load post page: ${res.status}`);
  }

  return await res.text();
}

function extractMediaIdFromHtml(html) {
  // Try several common patterns Instagram embeds
  const patterns = [
    /"media_id":"(\d+)"/,
    /"pk":"(\d+)"/,
    /"id":"(\d+)_(\d+)"/,
    /instagram:\/\/media\?id=(\d+)/,
    /"shortcode_media":\s*{\s*"id":\s*"(\d+)"/,
  ];

  for (const re of patterns) {
    const m = html.match(re);
    if (m) return m[1];
  }

  // Also try looking inside script tags for JSON
  const scriptMatches = html.match(/<script type="application\/json"[^>]*>(.*?)<\/script>/gs) || [];
  for (const script of scriptMatches) {
    try {
      const data = JSON.parse(script.replace(/<\/?script[^>]*>/g, ''));
      // Deep search for media id
      const str = JSON.stringify(data);
      const idMatch = str.match(/"id":"(\d{15,})"/);
      if (idMatch) return idMatch[1];
    } catch {}
  }

  return null;
}

function extractInitialCommentsFromHtml(html) {
  const comments = [];
  try {
    // Look for edge_media_to_parent_comment or similar
    const match = html.match(/"edge_media_to_parent_comment":\s*({.*?})\s*,\s*"/s) ||
                  html.match(/"edge_media_to_comment":\s*({.*?})\s*,\s*"/s);

    if (match) {
      const data = JSON.parse(match[1]);
      const edges = data.edges || [];
      for (const edge of edges) {
        const node = edge.node;
        if (node && node.owner) {
          comments.push({
            id: node.id || node.pk || String(Math.random()),
            user: node.owner.username || 'unknown',
            text: node.text || '',
            timestamp: node.created_at || null,
            isReply: false,
            tags: countTags(node.text || ''),
          });
        }
      }
    }
  } catch (e) {
    console.warn('Could not parse initial comments from HTML:', e.message);
  }
  return comments;
}

function countTags(text) {
  const matches = text.match(/@[a-zA-Z0-9._]+/g) || [];
  return matches.length;
}

async function fetchCommentsGraphQL(mediaId, cursor = null, sortOrder = 'recent') {
  const variables = {
    after: cursor,
    before: null,
    first: 50,
    last: null,
    media_id: mediaId,
    sort_order: sortOrder,
  };

  const body = new URLSearchParams({
    variables: JSON.stringify(variables),
    doc_id: DOC_ID_COMMENTS,
  });

  const res = await fetch('https://www.instagram.com/api/graphql', {
    method: 'POST',
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-IG-App-ID': '936619743392459',
      'X-Requested-With': 'XMLHttpRequest',
      'Accept': '*/*',
      'Origin': 'https://www.instagram.com',
      'Referer': 'https://www.instagram.com/',
    },
    body: body.toString(),
    timeout: 12000,
  });

  if (!res.ok) {
    throw new Error(`GraphQL request failed: ${res.status}`);
  }

  const json = await res.json();
  return json;
}

async function getAllComments(postUrl, maxPages = 12) {
  const shortcode = extractShortcode(postUrl);
  if (!shortcode) {
    throw new Error('Invalid Instagram URL. Please use a post or Reel link.');
  }

  console.log(`Fetching comments for shortcode: ${shortcode}`);

  // 1. Load the page to get media_id + initial comments
  const html = await fetchPostPage(shortcode);
  let mediaId = extractMediaIdFromHtml(html);
  let comments = extractInitialCommentsFromHtml(html);

  console.log(`Initial comments from HTML: ${comments.length}, mediaId: ${mediaId}`);

  // If we couldn't get mediaId, try a different approach
  if (!mediaId) {
    // Fallback: try to find it via embed or other methods
    const altMatch = html.match(/\/p\/([A-Za-z0-9_-]+)/);
    if (!altMatch) {
      throw new Error('Could not extract media ID from the post. The post may be private or Instagram changed their page structure.');
    }
  }

  // 2. Paginate via GraphQL (best effort)
  // Note: Without a proper session this often returns limited results.
  // We still try both popular and recent sorts.

  const seen = new Set(comments.map(c => c.id));
  let cursor = null;
  let pages = 0;

  // Try recent first
  while (pages < maxPages) {
    try {
      if (!mediaId) break;

      const data = await fetchCommentsGraphQL(mediaId, cursor, 'recent');
      const edges = data?.data?.xdt_api__v1__media__media_id__comments__connection?.edges ||
                    data?.data?.media?.edge_media_to_parent_comment?.edges ||
                    data?.data?.shortcode_media?.edge_media_to_parent_comment?.edges ||
                    [];

      if (!edges.length) break;

      for (const edge of edges) {
        const node = edge.node;
        if (!node) continue;
        const id = node.id || node.pk || node.pk_id;
        if (seen.has(id)) continue;
        seen.add(id);

        comments.push({
          id: String(id),
          user: node.user?.username || node.owner?.username || 'unknown',
          text: node.text || '',
          timestamp: node.created_at || node.created_at_utc || null,
          isReply: false,
          tags: countTags(node.text || ''),
        });
      }

      const pageInfo = data?.data?.xdt_api__v1__media__media_id__comments__connection?.page_info ||
                       data?.data?.media?.edge_media_to_parent_comment?.page_info;

      if (!pageInfo?.has_next_page) break;
      cursor = pageInfo.end_cursor;
      pages++;

      // Small delay to be polite
      await new Promise(r => setTimeout(r, 400 + Math.random() * 300));
    } catch (err) {
      console.warn('GraphQL pagination stopped:', err.message);
      break;
    }
  }

  // Deduplicate by user+text just in case
  const unique = [];
  const keySet = new Set();
  for (const c of comments) {
    const key = `${c.user.toLowerCase()}|${c.text.slice(0, 80)}`;
    if (!keySet.has(key)) {
      keySet.add(key);
      unique.push(c);
    }
  }

  return {
    shortcode,
    mediaId,
    total: unique.length,
    comments: unique,
    note: unique.length < 50
      ? 'Instagram limits anonymous access. For larger posts you may only get a partial list.'
      : null,
  };
}

// ========== API Routes ==========

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

app.post('/api/comments', async (req, res) => {
  try {
    const { url } = req.body;
    if (!url || typeof url !== 'string') {
      return res.status(400).json({ error: 'Please provide a valid Instagram post or Reel URL.' });
    }

    if (!url.includes('instagram.com')) {
      return res.status(400).json({ error: 'URL must be an Instagram post or Reel link.' });
    }

    const result = await getAllComments(url.trim());

    res.json({
      success: true,
      shortcode: result.shortcode,
      total: result.total,
      comments: result.comments,
      note: result.note,
    });
  } catch (err) {
    console.error('Error fetching comments:', err);
    res.status(500).json({
      success: false,
      error: err.message || 'Failed to fetch comments. The post may be private, deleted, or Instagram is blocking the request.',
    });
  }
});

// Serve frontend for all other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Instagram Winner Picker running on port ${PORT}`);
});
