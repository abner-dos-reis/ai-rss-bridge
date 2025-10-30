from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import json
from bs4 import BeautifulSoup
from ai_providers import get_ai_provider
from database import DatabaseManager
from rss_generator import generate_rss_xml, get_rss_link
from scheduler import get_scheduler
from config_manager import ConfigManager
from smart_scraper import scrape_with_patterns
import threading
import time
from datetime import datetime

# Try to import cloudscraper for bypassing Cloudflare
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
    print("✓ cloudscraper available - can bypass Cloudflare protection")
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    print("✗ cloudscraper not available - install with: pip install cloudscraper")

app = Flask(__name__)
CORS(app)
db = DatabaseManager("/app/data/feeds.db")
config_manager = ConfigManager()
scheduler = get_scheduler(db)

# Create a session with retry strategy
def create_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 504)
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def check_native_rss_feed(url, response_content):
    """Try to detect if site has native RSS feed"""
    try:
        soup = BeautifulSoup(response_content, 'html.parser')
        
        # Look for RSS/Atom feed links in head
        rss_links = []
        for link in soup.find_all('link', type=['application/rss+xml', 'application/atom+xml']):
            href = link.get('href')
            if href:
                rss_links.append(href)
        
        if rss_links:
            print(f"Found native RSS feeds: {rss_links}")
            return rss_links
    except:
        pass
    return None

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint to verify backend is running
    """
    return jsonify({
        "status": "ok",
        "message": "Backend is running",
        "cloudscraper": CLOUDSCRAPER_AVAILABLE
    }), 200

# Ensure all responses are JSON for API routes
@app.before_request
def before_request():
    # Force JSON responses for all API routes
    if request.path.startswith('/api/'):
        if not request.is_json and request.method in ['POST', 'PUT', 'PATCH']:
            if request.content_type != 'application/json':
                return jsonify({"error": "Content-Type must be application/json"}), 400

@app.after_request
def after_request(response):
    # Ensure API routes return JSON only if they're actually HTML errors
    if request.path.startswith('/api/'):
        if response.content_type.startswith('text/html') and response.status_code >= 400:
            # Only convert HTML error responses to JSON
            error_data = {"error": "Internal server error - HTML response detected", "status": response.status_code}
            return jsonify(error_data), response.status_code
    return response

# Global error handler to ensure all API responses are JSON
@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({"error": "API endpoint not found"}), 404
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error", "details": str(error)}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    # Log the error for debugging
    print(f"Unhandled exception: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
    
    # For non-HTTP exceptions, return JSON error
    return jsonify({
        "error": f"Unexpected error: {str(e)}", 
        "type": type(e).__name__
    }), 500

def try_ai_with_fallback(ai_provider_name, url, html_content):
    """
    Try AI extraction with multiple API keys if available
    Returns (result, api_key_used) or (error_dict, None)
    """
    all_keys = config_manager.get_all_api_keys(ai_provider_name)
    
    if not all_keys:
        return {"error": f"No API keys configured for {ai_provider_name}"}, None
    
    print(f"Trying {len(all_keys)} API key(s) for {ai_provider_name}")
    
    last_error = {"error": "Unknown error"}
    for i, api_key in enumerate(all_keys):
        print(f"Attempting with API key #{i+1}/{len(all_keys)}")
        try:
            provider = get_ai_provider(ai_provider_name, api_key)
            result = provider.extract_content(url, html_content)
            
            # CRITICAL FIX: Check if result is a tuple (should never happen but happens with some providers)
            if isinstance(result, tuple):
                print(f"⚠️ WARNING: Provider {ai_provider_name} returned tuple instead of dict! Converting...")
                result = result[0] if result and len(result) > 0 else {"error": "Provider returned empty tuple"}
            
            if not isinstance(result, dict):
                print(f"❌ ERROR: Provider {ai_provider_name} returned {type(result).__name__} instead of dict!")
                last_error = {"error": f"Provider returned invalid type: {type(result).__name__}"}
                continue
            
            if "error" not in result:
                print(f"✓ Success with API key #{i+1}")
                return result, api_key
            else:
                print(f"✗ API key #{i+1} failed: {result['error']}")
                last_error = result
        except Exception as e:
            print(f"✗ API key #{i+1} exception: {str(e)}")
            last_error = {"error": str(e)}
    
    # All keys failed
    print(f"❌ All {len(all_keys)} API key(s) failed for {ai_provider_name}")
    return last_error, None

def extract_structured_content_from_html(soup, url):
    """
    Extract structured content (articles with titles, links, images, dates) from HTML
    Returns formatted string for AI processing
    """
    # Try to find article elements with common patterns
    articles = []
    
    # Look for article elements
    articles.extend(soup.find_all(['article']))
    
    # Look for divs with article-like classes
    article_divs = soup.find_all('div', class_=lambda x: x and any(
        keyword in x.lower() for keyword in ['post', 'article', 'news', 'entry', 'item', 'story', 'blog']
    ))
    articles.extend(article_divs)
    
    # Look for list items that might be articles
    li_articles = soup.find_all('li', class_=lambda x: x and any(
        keyword in x.lower() for keyword in ['post', 'article', 'news', 'entry', 'item']
    ))
    articles.extend(li_articles)
    
    print(f"Found {len(articles)} total article elements")
    
    # Build structured content
    structured_content = []
    base_domain = '/'.join(url.split('/')[:3])  # Get base domain
    
    if articles:
        for i, article in enumerate(articles[:15]):  # Limit to first 15
            # Extract title
            title_elem = article.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            title = title_elem.get_text().strip() if title_elem else f"Article {i+1}"
            
            # Extract link
            link_elem = article.find('a', href=True)
            link = ""
            if link_elem:
                href = link_elem['href']
                if href.startswith('http'):
                    link = href
                elif href.startswith('/'):
                    link = base_domain + href
                else:
                    link = url + '/' + href.lstrip('/')
            
            # Extract date
            date_text = ""
            time_elem = article.find('time', datetime=True)
            if time_elem:
                date_text = time_elem.get('datetime', time_elem.get_text().strip())
            else:
                date_elem = article.find(['time', 'span', 'div'], class_=lambda x: x and any(
                    keyword in str(x).lower() for keyword in ['date', 'time', 'published', 'created', 'updated', 'post-date']
                ))
                if date_elem:
                    date_text = date_elem.get_text().strip()
            
            print(f"Found article: {title[:50]}... | Date: {date_text}")
            
            # Extract image with comprehensive strategy
            img_elem = None
            img_candidates = []
            
            # Strategy 1: og:image meta tag
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                img_candidates.append(('og:image', og_image['content']))
            
            # Strategy 2: Images in absolute positioned divs
            absolute_divs = article.find_all('div', class_=lambda x: x and any(
                'absolute' in str(x).lower() for x in [x] if x
            ))
            for div in absolute_divs:
                img = div.find('img', src=True)
                if img and img.get('src'):
                    img_candidates.append(('absolute-div', img['src']))
                    break
            
            # Strategy 3: Featured/thumbnail images with srcset support
            featured_img = article.find('img', class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['featured', 'thumbnail', 'cover', 'hero', 'main', 'banner']
            ))
            if featured_img:
                srcset = featured_img.get('srcset', '')
                if srcset:
                    srcs = [s.strip().split(' ')[0] for s in srcset.split(',')]
                    if srcs:
                        img_candidates.append(('featured-srcset', srcs[-1]))
                elif featured_img.get('src'):
                    img_candidates.append(('featured', featured_img['src']))
            
            # Strategy 4: Images in common wrapper classes
            for wrapper_class in ['image-wrapper', 'post-image', 'article-image', 'media', 'visual', 'wp-post-image']:
                wrapper = article.find(class_=lambda x: x and wrapper_class in str(x).lower())
                if wrapper:
                    img = wrapper.find('img', src=True)
                    if img:
                        img_candidates.append(('wrapper', img['src']))
                        break
            
            # Strategy 5: Picture element
            picture = article.find('picture')
            if picture:
                source = picture.find('source', srcset=True)
                if source:
                    img_candidates.append(('picture-source', source['srcset'].split(',')[0].strip().split(' ')[0]))
                img_in_picture = picture.find('img', src=True)
                if img_in_picture:
                    img_candidates.append(('picture-img', img_in_picture['src']))
            
            # Strategy 6: First significant image (within article element)
            for img in article.find_all('img', src=True):
                src = img.get('src', '')
                alt = img.get('alt', '').lower()
                width = img.get('width', '')
                height = img.get('height', '')
                
                # Skip small images, icons, and logos
                if any(keyword in src.lower() for keyword in ['icon', 'logo', 'avatar', 'emoji', 'spinner', 'pixel', '1x1']):
                    continue
                if any(keyword in alt for keyword in ['icon', 'logo', 'avatar', 'emoji']):
                    continue
                try:
                    if width and int(width) < 100:
                        continue
                    if height and int(height) < 100:
                        continue
                except:
                    pass
                
                img_candidates.append(('first-valid', src))
                break
            
            # Choose best image candidate
            image = ""
            if img_candidates:
                strategy, src = img_candidates[0]  # Prioritize by order added
                print(f"Selected image via strategy: {strategy}")
                
                # Normalize URL
                if src.startswith('//'):
                    image = 'https:' + src
                elif src.startswith('http'):
                    image = src
                elif src.startswith('/'):
                    image = base_domain + src
                elif not src.startswith('data:'):
                    image = base_domain + '/' + src.lstrip('/')
            
            # Get content preview
            content = article.get_text().strip()[:400]  # First 400 chars
            
            if title and len(title) > 3:  # Only include if we have a meaningful title
                structured_content.append(f"""
ARTICLE {i+1}:
TITLE: {title}
LINK: {link}
DATE: {date_text}
IMAGE: {image}
CONTENT: {content}
---""")
    
    if structured_content:
        return "\n".join(structured_content)
    else:
        # Fallback to main content
        main_content = soup.find(['main', 'div'], class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['content', 'main', 'body', 'wrapper']
        ))
        if main_content:
            return main_content.get_text()
        else:
            return soup.get_text()

@app.route('/api/diagnostics', methods=['GET'])
def diagnostics():
    """
    Diagnostic endpoint to check system capabilities
    """
    import sys
    import pkg_resources
    
    diagnostics_info = {
        "python_version": sys.version,
        "cloudscraper_available": CLOUDSCRAPER_AVAILABLE,
        "installed_packages": {},
        "fetch_strategies": []
    }
    
    # Check installed packages
    important_packages = ['cloudscraper', 'requests', 'beautifulsoup4', 'lxml', 'flask']
    for package in important_packages:
        try:
            version = pkg_resources.get_distribution(package).version
            diagnostics_info["installed_packages"][package] = version
        except:
            diagnostics_info["installed_packages"][package] = "NOT INSTALLED"
    
    # List available fetch strategies
    if CLOUDSCRAPER_AVAILABLE:
        diagnostics_info["fetch_strategies"].append("Cloudscraper (Cloudflare bypass)")
    diagnostics_info["fetch_strategies"].extend([
        "Session with full headers",
        "Direct request with headers",
        "Simple request"
    ])
    
    return jsonify(diagnostics_info)

@app.route('/api/info', methods=['GET'])
def api_info():
    """
    Returns API information and supported AI providers
    """
    return jsonify({
        "name": "AI RSS Bridge",
        "version": "1.0.0",
        "description": "Generate RSS feeds from any website using AI",
        "supported_providers": ["openai", "gemini", "claude", "perplexity"],
        "endpoints": {
            "/api/generate": "POST - Generate RSS feed from URL",
            "/api/feeds": "GET - List all generated feeds",
            "/api/rss/{feed_id}": "GET - Access RSS XML for specific feed"
        },
        "required_fields": {
            "url": "Website URL to generate RSS from",
            "ai_provider": "AI provider (openai, gemini, claude, perplexity)",
            "api_key": "API key for the selected AI provider"
        }
    })

@app.route('/api/generate', methods=['POST'])
def generate_rss():
    """
    Generate RSS feed from website URL using AI
    """
    print(f"=== Generate RSS Request Started ===")
    
    try:
        data = request.get_json()
        
        if not data:
            print("ERROR: No JSON data provided")
            return jsonify({"error": "No JSON data provided"}), 400
        
        url = data.get('url')
        ai_provider = data.get('ai_provider')
        api_key = data.get('api_key')
        
        print(f"Request data: URL={url}, Provider={ai_provider}")
        
        if not url or not ai_provider:
            print("ERROR: Missing required fields")
            return jsonify({
                "error": "Missing required fields",
                "required": ["url", "ai_provider"],
                "received": {"url": bool(url), "ai_provider": bool(ai_provider)}
            }), 400
        
        # Use saved API key if not provided
        if not api_key:
            api_key = config_manager.get_api_key(ai_provider)
            if not api_key:
                return jsonify({
                    "error": f"No API key found for {ai_provider}",
                    "message": "Please provide api_key in request or save it in config",
                    "config_endpoint": "/api/config/api-keys"
                }), 400
        
        # Check if feed already exists
        existing_feed = db.get_feed_by_url(url)
        if existing_feed:
            feed_id = existing_feed['id']
            rss_link = get_rss_link(feed_id)
            return jsonify({
                "message": "Feed already exists",
                "feed_id": feed_id,
                "rss_link": rss_link,
                "feed_info": existing_feed
            })
        
        # Check cache first to avoid being blocked
        cached = db.get_cached_content(url)
        if cached:
            print(f"=== Using cached content for {url} ===")
            print(f"Cached at: {cached['cached_at']}, Expires: {cached['expires_at']}")
            html_content = cached['content']
        else:
            print(f"=== No cache found, fetching {url} ===")
            
            # Fetch website content with realistic browser headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'Referer': 'https://www.google.com/'
            }
            
            # Check if we have a saved session for this site
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            saved_session = db.get_site_session(base_url)
        
            cookies = None
            if saved_session and saved_session.get('logged_in'):
                print(f"=== Using saved session for {base_url} ===")
                print(f"Session name: {saved_session.get('site_name')}")
                print(f"Session last validated: {saved_session.get('last_validated')}")
                cookies = saved_session.get('cookies')
                if cookies:
                    print(f"Found {len(cookies)} cookies in saved session")
                if saved_session.get('headers'):
                    print(f"Found custom headers in saved session")
                    headers.update(saved_session.get('headers'))
            else:
                print(f"=== No saved session found for {base_url} ===")
                print(f"You can add a login session in the 'Login Sessions' tab")
            
            print(f"=== Fetching URL: {url} ===")
            print(f"Cloudscraper available: {CLOUDSCRAPER_AVAILABLE}")
            print(f"Using saved cookies: {bool(cookies)}")
            if cookies:
                print(f"🍪 Found {len(cookies)} saved cookies")
            response = None
            
            # Try multiple strategies to fetch the website
            strategies = []
            
            # Strategy 0: Cloudscraper with saved session cookies (PRIORITY for logged sites)
            if CLOUDSCRAPER_AVAILABLE and cookies and saved_session:
                def cloudscraper_with_session():
                    print(f"🔐 Using Cloudscraper WITH saved login session")
                    scraper = cloudscraper.create_scraper(
                        browser={
                            'browser': 'chrome',
                            'platform': 'windows',
                            'desktop': True
                        }
                    )
                    # Add ALL cookies from saved session
                    scraper.cookies.update(cookies)
                    
                    # Add session headers if available
                    session_headers = headers.copy()
                    if saved_session.get('headers'):
                        session_headers.update(saved_session.get('headers'))
                    
                    return scraper.get(url, headers=session_headers, timeout=20, allow_redirects=True)
                strategies.append(("Cloudscraper + Saved Session (logged in)", cloudscraper_with_session))
            
            # Strategy 1: Cloudscraper with Chrome (best for Cloudflare/anti-bot protection)
            if CLOUDSCRAPER_AVAILABLE:
                def cloudscraper_chrome():
                    scraper = cloudscraper.create_scraper(
                        browser={
                            'browser': 'chrome',
                            'platform': 'windows',
                            'desktop': True
                        }
                    )
                    if cookies:
                        scraper.cookies.update(cookies)
                    return scraper.get(url, timeout=20, allow_redirects=True)
                strategies.append(("Cloudscraper Chrome/Windows", cloudscraper_chrome))
                
                # Strategy 1b: Cloudscraper with Firefox (alternative browser)
                def cloudscraper_firefox():
                    scraper = cloudscraper.create_scraper(
                        browser={
                            'browser': 'firefox',
                            'platform': 'linux',
                            'desktop': True
                        }
                    )
                    if cookies:
                        scraper.cookies.update(cookies)
                    return scraper.get(url, timeout=20, allow_redirects=True)
                strategies.append(("Cloudscraper Firefox/Linux", cloudscraper_firefox))
            
            # Strategy 2: Session with full headers and cookies
            def session_fetch():
                session = create_session()
                if cookies:
                    session.cookies.update(cookies)
                return session.get(url, headers=headers, timeout=15, allow_redirects=True)
            strategies.append(("Session with full headers", session_fetch))
            
            # Strategy 3: Session with varied User-Agent (for restrictive sites)
            def varied_session_fetch():
                session = create_session()
                varied_headers = headers.copy()
                varied_headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
                if cookies:
                    session.cookies.update(cookies)
                return session.get(url, headers=varied_headers, timeout=15, allow_redirects=True)
            strategies.append(("Session with Safari User-Agent", varied_session_fetch))
            
            # Strategy 4: Direct request with headers and cookies
            def direct_fetch():
                return requests.get(url, headers=headers, cookies=cookies, timeout=15, allow_redirects=True)
            strategies.append(("Direct request with headers", direct_fetch))
            
            # Strategy 5: Minimal headers (for over-protective sites)
            def minimal_fetch():
                minimal_headers = {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
                return requests.get(url, headers=minimal_headers, timeout=15, allow_redirects=True)
            strategies.append(("Minimal headers (Firefox)", minimal_fetch))
            
            # Strategy 6: Request without redirects (some sites block on redirect)
            def no_redirect_fetch():
                return requests.get(url, headers=headers, timeout=15, allow_redirects=False)
            strategies.append(("No redirects", no_redirect_fetch))
            
            # Strategy 7: Simple request (last resort)
            strategies.append(("Simple request", lambda: requests.get(url, timeout=15)))
            
            last_error = None
            print(f"Will try {len(strategies)} strategies in order:")
            for i, (name, _) in enumerate(strategies, 1):
                print(f"  {i}. {name}")
            print("")
            
            import time
            for i, (strategy_name, strategy_func) in enumerate(strategies):
                # Add small delay between attempts (except first one)
                if i > 0:
                    time.sleep(0.5)  # 500ms delay to avoid rate limiting
                    
                try:
                    print(f"▶ Trying strategy: {strategy_name}...")
                    response = strategy_func()
                    response.raise_for_status()
                    print(f"✓ SUCCESS with '{strategy_name}' - Status: {response.status_code}, Size: {len(response.content)} bytes")
                    break
                except requests.exceptions.HTTPError as http_err:
                    status = response.status_code if response else 'N/A'
                    print(f"✗ FAILED: {strategy_name} - HTTP {status}: {http_err}")
                    last_error = http_err
                    if response and response.status_code == 403:
                        # Check if session expired
                        if saved_session:
                            db.mark_session_logged_out(base_url)
                        continue  # Try next strategy
                    elif response and response.status_code >= 400:
                        break  # Don't retry for other client errors
                except requests.exceptions.RequestException as req_err:
                    print(f"✗ FAILED: {strategy_name} - Request error: {req_err}")
                    last_error = req_err
                    continue
            
            print(f"\n=== Fetch Result ===")
            if response is None or response.status_code >= 400:
                print(f"❌ All strategies failed!")
                error_msg = f"Failed to fetch website: {last_error}"
                if response and response.status_code == 403:
                    # Try to find RSS feed automatically
                    print("🔍 Site blocked, checking for native RSS feed...")
                    possible_feeds = [
                        f"{url.rstrip('/')}/feed/",
                        f"{url.rstrip('/')}/rss/",
                        f"{url.rstrip('/')}/feed.xml",
                        f"{url.rstrip('/')}/rss.xml",
                        f"{base_url}/feed/",
                        f"{base_url}/rss/"
                    ]
                    
                    found_feed = None
                    for feed_url in possible_feeds:
                        try:
                            print(f"  Checking: {feed_url}")
                            feed_response = requests.get(feed_url, headers={'User-Agent': headers['User-Agent']}, timeout=5)
                            if feed_response.status_code == 200 and ('xml' in feed_response.headers.get('content-type', '').lower() or 
                                                                      b'<rss' in feed_response.content[:500] or 
                                                                      b'<feed' in feed_response.content[:500]):
                                found_feed = feed_url
                                print(f"  ✓ Found RSS feed: {feed_url}")
                                break
                        except:
                            continue
                    
                    if found_feed:
                        error_msg = f"⛔ Website blocks automated access, but found official RSS feed!\n\n"
                        error_msg += f"✅ Use this URL instead: {found_feed}\n\n"
                        error_msg += "Try generating the feed again with this RSS URL."
                    else:
                        error_msg = "⛔ This website blocks automated access (403 Forbidden).\n\n"
                        error_msg += "💡 What you can try:\n"
                        error_msg += "1. Check if the site has an official RSS feed:\n"
                        error_msg += f"   • {url.rstrip('/')}/feed/\n"
                        error_msg += f"   • {url.rstrip('/')}/rss/\n"
                        error_msg += f"   • {url.rstrip('/')}/feed.xml\n"
                    error_msg += "2. Try a specific article page instead of the homepage\n"
                    error_msg += "3. Check system capabilities at: /api/diagnostics\n"
                    if not CLOUDSCRAPER_AVAILABLE:
                        error_msg += "4. ⚠️  Cloudscraper NOT installed - rebuild container with: docker-compose up --build\n"
                    else:
                        error_msg += "4. ✓ Cloudscraper is installed but site still blocks access\n"
                    error_msg += "\n⚙️ Some sites have very strict protection:\n"
                    error_msg += "• Use their official RSS feed if available\n"
                    error_msg += "• Try individual article URLs\n"
                    
                    # Special case suggestions
                    if 'deeplearning.ai' in url.lower():
                        error_msg += "\n🎓 DeepLearning.AI has very strict anti-bot protection.\n"
                        error_msg += "Unfortunately, this site blocks automated access even with Cloudscraper.\n\n"
                        error_msg += "📋 What you can try:\n"
                        error_msg += "1. Check their official blog RSS feed (if it exists)\n"
                        error_msg += "2. Subscribe via their newsletter instead\n"
                        error_msg += "3. Try accessing a specific article URL\n"
                        error_msg += "4. Use a browser extension to generate RSS\n\n"
                        error_msg += "⚙️ This is a limitation of web scraping - some sites are intentionally\n"
                        error_msg += "   designed to prevent automated access.\n"
                    
                    error_msg += f"\n📋 Technical: {last_error}"
                print(f"All strategies failed: {error_msg}")
                return jsonify({"error": error_msg}), 400
            
            # Save successful fetch to cache (24 hours for most sites, 6 hours for blogs)
            cache_hours = 6 if 'blog' in url.lower() or 'news' in url.lower() else 24
            db.save_cached_content(url, response.text, response.status_code, cache_hours)
            print(f"✓ Content cached for {cache_hours} hours")
            html_content = response.text
        
        # Check for native RSS feeds
        native_feeds = check_native_rss_feed(url, html_content.encode() if isinstance(html_content, str) else html_content)
        if native_feeds:
            print(f"⚠️  Native RSS feeds detected: {native_feeds}")
            # Continue anyway but log that native feeds exist
        
        # Parse HTML with better error handling
        try:
            # Try lxml first for better performance and HTML handling
            soup = BeautifulSoup(html_content, 'lxml')
        except:
            try:
                # Fallback to html.parser
                soup = BeautifulSoup(html_content, 'html.parser')
            except Exception as parse_error:
                return jsonify({"error": f"Failed to parse HTML: {str(parse_error)}"}), 400
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "aside", "form", "button"]):
            script.decompose()
        
        # Try to find article elements with common patterns
        articles = []
        
        # Look for article elements
        articles.extend(soup.find_all(['article']))
        print(f"Found {len(articles)} <article> elements")
        
        # Look for divs with article-like classes
        article_divs = soup.find_all('div', class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['post', 'article', 'news', 'entry', 'item', 'story', 'blog']
        ))
        articles.extend(article_divs)
        print(f"Found {len(article_divs)} article-like <div> elements (total: {len(articles)})")
        
        # Look for list items that might be articles
        li_articles = soup.find_all('li', class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['post', 'article', 'news', 'entry', 'item']
        ))
        articles.extend(li_articles)
        print(f"Found {len(li_articles)} article-like <li> elements (total: {len(articles)})")
        
        # Use helper function to extract structured content
        html_content = extract_structured_content_from_html(soup, url)
        
        # Clean up whitespace
        html_content = ' '.join(html_content.split())
        print(f"HTML content length: {len(html_content)} characters")
        print(f"HTML content preview: {html_content[:300]}...")
        
        # Get AI provider and extract content with fallback
        print(f"Calling AI provider: {ai_provider}")
        
        # Try with provided api_key first, then fallback to saved keys
        if api_key:
            print("Using provided API key")
            provider = get_ai_provider(ai_provider, api_key)
            ai_result = provider.extract_content(url, html_content)
            print(f"⚠️ CHECKPOINT 1: After extract_content, type = {type(ai_result)}")
            if isinstance(ai_result, tuple):
                print(f"⚠️ CHECKPOINT 1: It's a TUPLE! Content: {ai_result}")
            api_key_used = api_key
        else:
            print("Using saved API keys with fallback")
            ai_result, api_key_used = try_ai_with_fallback(ai_provider, url, html_content)
            print(f"⚠️ CHECKPOINT 2: After try_ai_with_fallback, type = {type(ai_result)}")
            if isinstance(ai_result, tuple):
                print(f"⚠️ CHECKPOINT 2: It's a TUPLE! Content: {ai_result}")
        
        print(f"AI result received: {type(ai_result)}")
        
        # Safety check: ensure ai_result is a dict
        if isinstance(ai_result, tuple):
            print(f"WARNING: ai_result is tuple, extracting first element: {ai_result}")
            ai_result = ai_result[0] if ai_result else {"error": "Invalid result format"}
        
        if not isinstance(ai_result, dict):
            print(f"ERROR: ai_result is not a dict: {type(ai_result)} = {ai_result}")
            return jsonify({"error": f"Invalid AI response format: {type(ai_result).__name__}"}), 500
        
        print(f"✓ ai_result is a valid dict with keys: {list(ai_result.keys())}")
        
        if "error" in ai_result:
            print(f"AI error: {ai_result['error']}")
            return jsonify({"error": ai_result["error"]}), 500
        
        # Extract patterns from the successful AI analysis
        try:
            # Simple pattern extraction fallback
            extraction_patterns = json.dumps({
                'base_url': '/'.join(url.split('/')[:3]),
                'article_patterns': ['article', 'div.post', 'div.entry'],
                'image_patterns': [{'selector': 'img', 'category': 'general'}]
            })
        except Exception as pattern_error:
            print(f"Warning: Pattern extraction failed: {pattern_error}")
            extraction_patterns = "{}"  # Empty JSON as fallback
        
        # Save to database with patterns
        try:
            print(f"Saving to database...")
            print(f"Extracting title from ai_result type={type(ai_result)}")
            
            # Extra safety: wrap .get() calls in try/except
            try:
                title = ai_result.get('title', 'AI Generated Feed')
                print(f"✓ Title extracted: {title}")
            except AttributeError as e:
                print(f"❌ ERROR: ai_result has no .get() method! Type: {type(ai_result)}, Value: {ai_result}")
                return jsonify({"error": f"Internal error: ai_result is {type(ai_result).__name__}, not dict"}), 500
            
            description = ai_result.get('description', 'Generated by AI RSS Bridge')
            items = ai_result.get('items', [])
            
            feed_id = db.save_feed(
                url=url,
                title=title,
                description=description,
                ai_provider=ai_provider,
                items=items,
                extraction_patterns=extraction_patterns
            )
            
            print(f"Feed saved with ID: {feed_id}")
            rss_link = get_rss_link(feed_id)
            
            result = {
                "message": "RSS feed generated successfully",
                "feed_id": feed_id,
                "rss_link": rss_link,
                "title": ai_result.get('title'),
                "description": ai_result.get('description'),
                "items_count": len(ai_result.get('items', []))
            }
            
            print(f"Returning success result: {result}")
            return jsonify(result)
            
        except Exception as db_error:
            print(f"Database error: {db_error}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"Failed to save feed: {str(db_error)}"}), 500
            
    except requests.RequestException as e:
        print(f"Request error: {e}")
        return jsonify({"error": f"Failed to fetch website: {str(e)}"}), 400
    except AttributeError as e:
        print(f"❌ ATTRIBUTE ERROR in generate_rss: {str(e)}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()
        
        # This is the tuple error - let's provide detailed info
        error_msg = f"Internal error: {str(e)}"
        if "'tuple' object has no attribute" in str(e):
            error_msg = "Internal error: AI provider returned invalid format (tuple instead of dict). This is a bug."
        
        return jsonify({
            "error": error_msg,
            "type": "AttributeError",
            "details": "Please report this error with the URL you tried to convert"
        }), 500
    except Exception as e:
        print(f"Unexpected error in generate_rss: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": f"Internal error: {str(e)}", 
            "type": type(e).__name__
        }), 500

@app.route('/api/feeds', methods=['GET'])
def list_feeds():
    """
    List all generated RSS feeds with their items
    """
    feeds = db.get_all_feeds()
    for feed in feeds:
        feed['rss_link'] = get_rss_link(feed['id'])
        # Include items for each feed
        feed['items'] = db.get_feed_items(feed['id'])
    
    return jsonify({
        "feeds": feeds,
        "total": len(feeds)
    })

@app.route('/api/feeds/<int:feed_id>/items', methods=['GET'])
def get_feed_items_endpoint(feed_id):
    """
    Get items for a specific feed
    """
    try:
        feed = db.get_feed_by_id(feed_id)
        if not feed:
            return jsonify({"error": "Feed not found"}), 404
        
        items = db.get_feed_items(feed_id)
        return jsonify({"items": items})
    except Exception as e:
        return jsonify({"error": f"Failed to get feed items: {str(e)}"}), 500

@app.route('/api/rss/<int:feed_id>', methods=['GET'])
def get_rss_xml(feed_id):
    """
    Get RSS XML for specific feed
    """
    # Get feed info
    feeds = db.get_all_feeds()
    feed_info = None
    for feed in feeds:
        if feed['id'] == feed_id:
            feed_info = feed
            break
    
    if not feed_info:
        return jsonify({"error": "Feed not found"}), 404
    
    # Check if site requires login and session is expired
    from urllib.parse import urlparse
    parsed_url = urlparse(feed_info['url'])
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    saved_session = db.get_site_session(base_url)
    
    # Get feed items
    items = db.get_feed_items(feed_id)
    
    # If session expired, add logout notification as first item
    if saved_session and not saved_session.get('logged_in'):
        logout_item = {
            'title': '🔒 Logged Out - Action Required',
            'link': feed_info['url'],
            'description': f'Your login session for {saved_session.get("site_name", base_url)} has expired. Please log in again to continue receiving feed updates.',
            'pub_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
            'image': None
        }
        items = [logout_item] + items
    
    # Generate RSS XML
    feed_data = {
        "title": feed_info['title'],
        "description": feed_info['description'],
        "url": feed_info['url'],
        "items": items
    }
    
    rss_xml = generate_rss_xml(feed_data)
    
    return Response(rss_xml, mimetype='application/rss+xml')

@app.route('/api/feeds/<int:feed_id>', methods=['DELETE'])
def delete_feed(feed_id):
    """
    Delete a specific feed
    """
    try:
        feed = db.get_feed_by_id(feed_id)
        if not feed:
            return jsonify({"error": "Feed not found"}), 404
        
        db.delete_feed(feed_id)
        return jsonify({"message": f"Feed '{feed['title']}' deleted successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to delete feed: {str(e)}"}), 500

@app.route('/api/feeds', methods=['DELETE'])
def delete_all_feeds():
    """
    Delete all feeds
    """
    try:
        db.delete_all_feeds()
        return jsonify({"message": "All feeds deleted successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to delete feeds: {str(e)}"}), 500

# Site Session Management Endpoints
@app.route('/api/sessions', methods=['GET'])
def get_all_sessions():
    """
    Get all site login sessions
    """
    try:
        sessions = db.get_all_site_sessions()
        return jsonify({"sessions": sessions})
    except Exception as e:
        return jsonify({"error": f"Failed to get sessions: {str(e)}"}), 500

@app.route('/api/sessions', methods=['POST'])
def save_session_route():
    """
    Create/save a site login session with cookies
    """
    data = request.get_json()
    
    site_url = data.get('site_url')
    site_name = data.get('site_name')
    cookies = data.get('cookies')
    headers = data.get('headers')
    
    if not site_url or not site_name:
        return jsonify({"error": "site_url and site_name are required"}), 400
    
    try:
        db.save_site_session(site_url, site_name, cookies, headers)
        return jsonify({"message": "Session saved successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to save session: {str(e)}"}), 500

@app.route('/api/sessions/<path:site_url>', methods=['DELETE'])
def delete_session(site_url):
    """
    Delete a site login session
    """
    try:
        db.delete_site_session(site_url)
        return jsonify({"message": "Session deleted successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to delete session: {str(e)}"}), 500

@app.route('/api/update/<int:feed_id>', methods=['POST'])
def update_feed(feed_id):
    """
    Update specific feed with fresh content using saved patterns (no AI needed)
    """
    try:
        # Get existing feed
        feed_info = db.get_feed_by_id(feed_id)
        if not feed_info:
            return jsonify({"error": "Feed not found"}), 404
        
        # Check if we have extraction patterns
        patterns = feed_info.get('extraction_patterns')
        if not patterns:
            return jsonify({
                "error": "No extraction patterns found for this feed",
                "message": "Please re-analyze with AI to create patterns",
                "suggestion": "Use 'Re-analyze with AI' button"
            }), 400
        
        # Use smart scraper with saved patterns
        scraper_result = scrape_with_patterns(feed_info['url'], patterns)
        
        if "error" in scraper_result:
            return jsonify({"error": scraper_result["error"]}), 500
        
        # Update database with new content (preserve patterns)
        db.update_feed(
            feed_id=feed_id,
            title=scraper_result.get('title', feed_info['title']),
            description=scraper_result.get('description', feed_info['description']),
            ai_provider=feed_info['ai_provider'],
            items=scraper_result.get('items', [])
        )
        
        return jsonify({
            "message": "Feed updated successfully using smart scraping",
            "title": scraper_result.get('title'),
            "description": scraper_result.get('description'),
            "items_count": len(scraper_result.get('items', [])),
            "method": "pattern_based_scraping"
        })
        
    except Exception as e:
        return jsonify({"error": f"Update failed: {str(e)}"}), 500

@app.route('/api/reanalyze/<int:feed_id>', methods=['POST'])
def reanalyze_feed(feed_id):
    """
    Re-analyze feed with AI to update extraction patterns
    """
    data = request.get_json()
    ai_provider = data.get('ai_provider')
    api_key = data.get('api_key')
    
    try:
        # Get existing feed
        feed_info = db.get_feed_by_id(feed_id)
        if not feed_info:
            return jsonify({"error": "Feed not found"}), 404
        
        # Use existing AI provider if not specified
        if not ai_provider:
            ai_provider = feed_info['ai_provider']
        
        # Use saved API key if not provided
        if not api_key:
            api_key = config_manager.get_api_key(ai_provider)
            if not api_key:
                return jsonify({
                    "error": f"No API key found for {ai_provider}",
                    "message": "Please provide api_key in request or save it in config"
                }), 400
        
        # Fetch fresh content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(feed_info['url'], headers=headers, timeout=10)
        response.raise_for_status()
        
        # Extract structured content like in generate_rss
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "aside", "form", "button"]):
            script.decompose()
        
        # Use helper function to extract structured content
        html_content = extract_structured_content_from_html(soup, feed_info['url'])
        print(f"HTML content length: {len(html_content)} characters")
        print(f"HTML content preview: {html_content[:300]}...")
        
        # Get AI provider and extract content with fallback
        if api_key:
            provider = get_ai_provider(ai_provider, api_key)
            ai_result = provider.extract_content(feed_info['url'], html_content)
        else:
            ai_result, _ = try_ai_with_fallback(ai_provider, feed_info['url'], html_content)
        
        # Safety check: ensure ai_result is a dict
        if isinstance(ai_result, tuple):
            print(f"WARNING: reanalyze got tuple, extracting first element: {ai_result}")
            ai_result = ai_result[0] if ai_result else {"error": "Invalid result format"}
        
        if not isinstance(ai_result, dict):
            print(f"ERROR: reanalyze ai_result is not a dict: {type(ai_result)} = {ai_result}")
            return jsonify({"error": f"Invalid AI response format: {type(ai_result).__name__}"}), 500
        
        print(f"✓ reanalyze ai_result is valid dict with keys: {list(ai_result.keys())}")
        
        if "error" in ai_result:
            return jsonify({"error": ai_result["error"]}), 500
        
        # Extract new patterns (simple fallback)
        extraction_patterns = json.dumps({
            'base_url': '/'.join(feed_info['url'].split('/')[:3]),
            'article_patterns': ['article', 'div.post', 'div.entry'],
            'image_patterns': [{'selector': 'img', 'category': 'general'}]
        })
        
        # Update database with new patterns and content
        try:
            title = ai_result.get('title', feed_info['title'])
            description = ai_result.get('description', feed_info['description'])
            items = ai_result.get('items', [])
        except AttributeError as e:
            print(f"❌ ERROR in reanalyze: ai_result has no .get()! Type: {type(ai_result)}, Value: {ai_result}")
            return jsonify({"error": f"Internal error: ai_result is {type(ai_result).__name__}, not dict"}), 500
        
        db.save_feed(
            url=feed_info['url'],
            title=title,
            description=description,
            ai_provider=ai_provider,
            items=items,
            extraction_patterns=extraction_patterns
        )
        
        return jsonify({
            "message": "Feed re-analyzed successfully with AI",
            "title": title,
            "description": description,
            "items_count": len(items),
            "method": "ai_reanalysis",
            "patterns_updated": True
        })
        
    except Exception as e:
        return jsonify({"error": f"Re-analysis failed: {str(e)}"}), 500

@app.route('/api/scheduler/status', methods=['GET'])
def scheduler_status():
    """
    Get scheduler status
    """
    return jsonify({
        "running": scheduler.running,
        "api_keys_configured": list(scheduler.api_keys.keys())
    })

@app.route('/api/scheduler/start', methods=['POST'])
def start_scheduler():
    """
    Start automatic feed updates
    """
    data = request.get_json()
    
    if not data or 'api_keys' not in data:
        return jsonify({
            "error": "API keys required",
            "format": {
                "api_keys": {
                    "openai": "your-openai-key",
                    "gemini": "your-gemini-key"
                }
            }
        }), 400
    
    # Set API keys for auto-updates
    for provider, api_key in data['api_keys'].items():
        if api_key:  # Only set non-empty keys
            scheduler.set_api_key(provider, api_key)
    
    scheduler.start_scheduler()
    
    return jsonify({
        "message": "Scheduler started",
        "providers_configured": list(scheduler.api_keys.keys())
    })

@app.route('/api/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """
    Stop automatic feed updates
    """
    scheduler.stop_scheduler()
    return jsonify({"message": "Scheduler stopped"})

# Configuration endpoints
@app.route('/api/config/api-keys', methods=['GET'])
def get_saved_api_keys():
    """
    Get list of saved API key providers with counts
    """
    print("=== GET SAVED API KEYS ===")
    try:
        providers = config_manager.get_saved_providers()
        
        # Get counts for each provider
        providers_info = {}
        for provider in providers:
            keys = config_manager.get_all_api_keys(provider)
            providers_info[provider] = len(keys)
        
        print(f"Found saved providers: {providers_info}")
        return jsonify({
            "saved_providers": providers,
            "providers_info": providers_info
        })
    except Exception as e:
        print(f"Error getting saved providers: {e}")
        return jsonify({"saved_providers": [], "error": str(e)})

@app.route('/api/config/api-keys/<provider>/all', methods=['GET'])
def get_all_keys_for_provider(provider):
    """
    Get all API keys for a specific provider (masked)
    """
    if provider not in ['openai', 'gemini', 'claude', 'perplexity']:
        return jsonify({"error": "Invalid provider"}), 400
    
    try:
        keys = config_manager.get_all_api_keys(provider)
        # Mask keys for security (show first 8 and last 4 characters)
        masked_keys = []
        for key in keys:
            if len(key) > 12:
                masked = key[:8] + "..." + key[-4:]
            else:
                masked = key[:4] + "..."
            masked_keys.append({"masked": masked, "full": key})
        
        return jsonify({"provider": provider, "keys": masked_keys, "count": len(keys)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/config/api-keys', methods=['POST'])
def save_api_key():
    """
    Save API key for a provider (supports multiple keys)
    """
    print("=== SAVE API KEY REQUEST ===")
    data = request.get_json()
    print(f"Received data: {data}")
    
    if not data or 'provider' not in data or 'api_key' not in data:
        print("Missing required fields")
        return jsonify({"error": "Provider and api_key required"}), 400
    
    provider = data['provider']
    api_key = data['api_key'].strip()
    
    if provider not in ['openai', 'gemini', 'claude', 'perplexity']:
        print(f"Invalid provider: {provider}")
        return jsonify({"error": "Invalid provider"}), 400
    
    if not api_key:
        return jsonify({"error": "API key cannot be empty"}), 400
    
    try:
        # Check if this API key already exists in ANY provider
        all_providers = ['openai', 'gemini', 'claude', 'perplexity']
        for check_provider in all_providers:
            existing_keys = config_manager.get_all_api_keys(check_provider)
            if api_key in existing_keys:
                print(f"❌ API key already exists in {check_provider}")
                return jsonify({
                    "error": f"This API key is already registered for {check_provider.upper()}"
                }), 400
        
        config_manager.save_api_key(provider, api_key)
        keys_count = len(config_manager.get_all_api_keys(provider))
        print(f"Successfully saved API key for {provider} (total: {keys_count})")
        return jsonify({
            "message": f"API key saved for {provider}",
            "total_keys": keys_count
        })
    except Exception as e:
        print(f"Error saving API key: {e}")
        return jsonify({"error": f"Failed to save API key: {str(e)}"}), 500

@app.route('/api/config/api-keys/<provider>', methods=['DELETE'])
def delete_api_key_route(provider):
    """
    Delete specific API key or all keys for a provider
    """
    if provider not in ['openai', 'gemini', 'claude', 'perplexity']:
        return jsonify({"error": "Invalid provider"}), 400
    
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception as e:
        print(f"Error parsing JSON in DELETE request: {e}")
        data = {}
    
    api_key = data.get('api_key')  # If provided, delete specific key
    
    config_manager.delete_api_key(provider, api_key)
    return jsonify({"message": f"API key(s) deleted for {provider}"})

@app.route('/api/config/theme', methods=['GET'])
def get_theme():
    """
    Get saved theme preference
    """
    theme = config_manager.get_theme()
    return jsonify({"theme": theme})

@app.route('/api/config/theme', methods=['POST'])
def save_theme():
    """
    Save theme preference
    """
    data = request.get_json()
    
    if not data or 'theme' not in data:
        return jsonify({"error": "Theme required"}), 400
    
    theme = data['theme']
    if theme not in ['light', 'dark']:
        return jsonify({"error": "Invalid theme. Use 'light' or 'dark'"}), 400
    
    config_manager.save_theme(theme)
    return jsonify({"message": f"Theme saved: {theme}"})

@app.route('/api/config/last-ai-provider', methods=['GET'])
def get_last_ai_provider():
    """
    Get last selected AI provider
    """
    provider = config_manager.get_last_ai_provider()
    return jsonify({"provider": provider})

@app.route('/api/config/last-ai-provider', methods=['POST'])
def save_last_ai_provider():
    """
    Save last selected AI provider
    """
    data = request.get_json()
    
    if not data or 'provider' not in data:
        return jsonify({"error": "Provider required"}), 400
    
    provider = data['provider']
    if provider not in ['openai', 'gemini', 'claude', 'perplexity']:
        return jsonify({"error": "Invalid provider"}), 400
    
    config_manager.save_last_ai_provider(provider)
    return jsonify({"message": f"Last AI provider saved: {provider}"})

@app.route('/api/test/gemini-models', methods=['GET'])
def test_gemini_models():
    """
    Test which Gemini models are available with the saved API key
    """
    try:
        # Buscar a API key do Gemini
        api_key = config_manager.get_api_key('gemini')
        if not api_key:
            return jsonify({"error": "No Gemini API key saved"}), 400
        
        # URL para listar modelos disponíveis
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        
        response = requests.get(list_url)
        
        if response.status_code == 200:
            data = response.json()
            available_models = []
            
            for model in data.get('models', []):
                model_name = model.get('name', '')
                supported_methods = model.get('supportedGenerationMethods', [])
                
                # Apenas modelos que suportam generateContent
                if 'generateContent' in supported_methods:
                    available_models.append({
                        'name': model_name,
                        'supported_methods': supported_methods
                    })
            
            return jsonify({
                "success": True,
                "available_models": available_models,
                "total_models": len(available_models)
            })
        else:
            return jsonify({
                "error": f"Failed to list models: {response.status_code}",
                "response": response.text
            }), 400
            
    except Exception as e:
        return jsonify({"error": f"Exception: {str(e)}"}), 500

# Legacy endpoint for backward compatibility
@app.route('/api/rss-bridge', methods=['POST'])
def rss_bridge():
    """
    Legacy endpoint - redirects to /api/info for field information
    """
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({
            "message": "Please use /api/generate endpoint",
            "redirect_to": "/api/info",
            "new_format": {
                "url": "Website URL",
                "ai_provider": "openai|gemini|claude|perplexity",
                "api_key": "Your AI provider API key"
            }
        }), 400
    
    # Redirect to new endpoint format
    return jsonify({
        "message": "Please use /api/generate endpoint with updated format",
        "redirect_to": "/api/generate"
    }), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8895, debug=True)
