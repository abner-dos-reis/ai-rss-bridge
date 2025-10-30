# 🛡️ Anti-Bot Protection & Troubleshooting

## Common Issues

### 403 Forbidden Error

Some websites block automated access to prevent bots. This is common on sites with:
- Cloudflare protection
- Custom anti-bot systems
- Rate limiting
- Authentication requirements

## Solutions

### 1. Use Official RSS Feeds (Recommended)

Many sites already provide RSS feeds. Try these common URLs:
- `https://example.com/feed`
- `https://example.com/rss`
- `https://example.com/feed.xml`
- `https://example.com/atom.xml`

### 2. Install Cloudscraper (For Cloudflare Bypass)

Cloudscraper can bypass many common anti-bot protections:

```bash
# In Docker container
docker exec -it ai-rss-bridge-backend-1 pip install cloudscraper

# Or add to requirements.txt and rebuild
pip install cloudscraper
```

### 3. Try Different Pages

Instead of the homepage, try:
- Blog listing pages (`/blog`, `/news`)
- Specific article pages
- Category pages

### 4. Sites Known to Work Well

✅ Sites that typically work:
- Medium blogs
- WordPress sites
- Ghost blogs
- Static sites
- Most personal blogs

⚠️ Sites that may have issues:
- Sites with Cloudflare
- Sites requiring JavaScript
- Sites with login requirements
- Enterprise/corporate sites with strict security

## Specific Site: DeepLearning.AI

**Issue:** `https://www.deeplearning.ai/blog/` returns 403 Forbidden

**Why:** The site has strong anti-bot protection (likely Cloudflare + custom rules)

**Solutions:**
1. **Use their official feed** (if available):
   - Try: `https://www.deeplearning.ai/feed`
   - Try: `https://www.deeplearning.ai/blog/feed`
   
2. **Use individual article URLs** instead of the blog listing page

3. **Contact DeepLearning.AI** to ask for official RSS feed access

4. **Alternative:** Use their newsletter or email notifications

## Future Improvements

Planned features to handle more sites:
- [ ] Browser automation (Playwright/Selenium)
- [ ] Proxy rotation support
- [ ] Configurable delays between requests
- [ ] Cookie/session persistence
- [ ] JavaScript rendering support

## Technical Details

The application tries multiple strategies in order:
1. **Cloudscraper** (if installed) - bypasses Cloudflare
2. **Session with full browser headers** - mimics real browser
3. **Direct request with headers** - standard approach
4. **Simple request** - fallback

Each strategy has:
- Realistic User-Agent
- Full browser headers (Accept, Accept-Language, etc.)
- Referer header
- Retry logic (3 attempts)
- 15-20 second timeout
