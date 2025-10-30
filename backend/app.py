from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
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

app = Flask(__name__)
CORS(app)
db = DatabaseManager("/app/data/feeds.db")
config_manager = ConfigManager()
scheduler = get_scheduler(db)

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
        
        # Fetch website content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML with better error handling
        try:
            # Try lxml first for better performance and HTML handling
            soup = BeautifulSoup(response.content, 'lxml')
        except:
            try:
                # Fallback to html.parser
                soup = BeautifulSoup(response.content, 'html.parser')
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
        
        # Build structured content
        structured_content = []
        base_domain = '/'.join(url.split('/')[:3])  # Get base domain
        
        if articles:
            for i, article in enumerate(articles[:15]):  # Limit to first 15
                # Try to find title
                title_elem = article.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                title = title_elem.get_text().strip() if title_elem else f"Article {i+1}"
                
                # Try to find link
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
                
                # Try to find date
                date_elem = article.find(['time', 'span'], class_=lambda x: x and any(
                    keyword in x.lower() for keyword in ['date', 'time', 'published', 'created']
                ))
                date_text = date_elem.get_text().strip() if date_elem else ""
                if not date_text:
                    date_elem = article.find(text=lambda x: x and any(
                        keyword in x.lower() for keyword in ['2023', '2024', '2025', 'october', 'september', 'november']
                    ))
                    date_text = str(date_elem).strip() if date_elem else ""
                
                # Try to find image with comprehensive strategy
                img_elem = None
                
                # Strategy 1: Look for images in absolute positioned divs (modern sites)
                absolute_divs = article.find_all('div', class_=lambda x: x and any(
                    'absolute' in ' '.join(x).lower() for x in [x] if x
                ))
                
                for div in absolute_divs:
                    img = div.find('img', src=True)
                    if img and img.get('src'):
                        img_elem = img
                        break
                
                # Strategy 2: Featured/thumbnail images
                if not img_elem:
                    img_elem = article.find('img', class_=lambda x: x and any(
                        keyword in ' '.join(x).lower() for keyword in ['featured', 'thumbnail', 'cover', 'hero', 'main']
                    ))
                
                # Strategy 3: Images in common wrapper classes
                if not img_elem:
                    for wrapper_class in ['image-wrapper', 'post-image', 'article-image', 'media', 'visual']:
                        wrapper = article.find(class_=lambda x: x and wrapper_class in ' '.join(x).lower())
                        if wrapper:
                            img_elem = wrapper.find('img', src=True)
                            if img_elem:
                                break
                
                # Strategy 4: First significant image
                if not img_elem:
                    for img in article.find_all('img', src=True):
                        src = img.get('src', '')
                        alt = img.get('alt', '').lower()
                        
                        # Skip small images, icons, and logos
                        if any(keyword in src.lower() for keyword in ['icon', 'logo', 'avatar', 'emoji', 'spinner']):
                            continue
                        if any(keyword in alt for keyword in ['icon', 'logo', 'avatar', 'emoji']):
                            continue
                        
                        img_elem = img
                        break
                
                image = ""
                if img_elem and img_elem.get('src'):
                    src = img_elem['src']
                    if src.startswith('http'):
                        image = src
                    elif src.startswith('/'):
                        image = base_domain + src
                    elif not src.startswith('data:'):
                        image = base_domain + '/' + src.lstrip('/')
                
                # Get content
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
            html_content = "\n".join(structured_content)
        else:
            # Fallback to main content
            main_content = soup.find(['main', 'div'], class_=lambda x: x and any(
                keyword in x.lower() for keyword in ['content', 'main', 'body', 'wrapper']
            ))
            if main_content:
                html_content = main_content.get_text()
            else:
                html_content = soup.get_text()
        
        # Clean up whitespace - não limitar tamanho aqui, deixar o AI provider fazer
        html_content = ' '.join(html_content.split())
        print(f"HTML content length: {len(html_content)} characters")
        print(f"HTML content preview: {html_content[:300]}...")
        
        # Get AI provider and extract content
        print(f"Calling AI provider: {ai_provider}")
        provider = get_ai_provider(ai_provider, api_key)
        print(f"Provider obtained: {provider}")
        
        ai_result = provider.extract_content(url, html_content)
        print(f"AI result received: {type(ai_result)}")
        
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
            feed_id = db.save_feed(
                url=url,
                title=ai_result.get('title', 'AI Generated Feed'),
                description=ai_result.get('description', 'Generated by AI RSS Bridge'),
                ai_provider=ai_provider,
                items=ai_result.get('items', []),
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
    
    # Get feed items
    items = db.get_feed_items(feed_id)
    
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
            
        html_content = ' '.join(soup.get_text().split())[:6000]
        
        # Get AI provider and extract content
        provider = get_ai_provider(ai_provider, api_key)
        ai_result = provider.extract_content(feed_info['url'], html_content)
        
        if "error" in ai_result:
            return jsonify({"error": ai_result["error"]}), 500
        
        # Extract new patterns (simple fallback)
        extraction_patterns = json.dumps({
            'base_url': '/'.join(feed_info['url'].split('/')[:3]),
            'article_patterns': ['article', 'div.post', 'div.entry'],
            'image_patterns': [{'selector': 'img', 'category': 'general'}]
        })
        
        # Update database with new patterns and content
        db.save_feed(
            url=feed_info['url'],
            title=ai_result.get('title', feed_info['title']),
            description=ai_result.get('description', feed_info['description']),
            ai_provider=ai_provider,
            items=ai_result.get('items', []),
            extraction_patterns=extraction_patterns
        )
        
        return jsonify({
            "message": "Feed re-analyzed successfully with AI",
            "title": ai_result.get('title'),
            "description": ai_result.get('description'),
            "items_count": len(ai_result.get('items', [])),
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
    Get list of saved API key providers
    """
    print("=== GET SAVED API KEYS ===")
    try:
        providers = config_manager.get_saved_providers()
        print(f"Found saved providers: {providers}")
        return jsonify({"saved_providers": providers})
    except Exception as e:
        print(f"Error getting saved providers: {e}")
        return jsonify({"saved_providers": [], "error": str(e)})

@app.route('/api/config/api-keys', methods=['POST'])
def save_api_key():
    """
    Save API key for a provider
    """
    print("=== SAVE API KEY REQUEST ===")
    data = request.get_json()
    print(f"Received data: {data}")
    
    if not data or 'provider' not in data or 'api_key' not in data:
        print("Missing required fields")
        return jsonify({"error": "Provider and api_key required"}), 400
    
    provider = data['provider']
    api_key = data['api_key']
    
    if provider not in ['openai', 'gemini', 'claude', 'perplexity']:
        print(f"Invalid provider: {provider}")
        return jsonify({"error": "Invalid provider"}), 400
    
    try:
        config_manager.save_api_key(provider, api_key)
        print(f"Successfully saved API key for {provider}")
        return jsonify({"message": f"API key saved for {provider}"})
    except Exception as e:
        print(f"Error saving API key: {e}")
        return jsonify({"error": f"Failed to save API key: {str(e)}"}), 500

@app.route('/api/config/api-keys/<provider>', methods=['DELETE'])
def delete_api_key(provider):
    """
    Delete saved API key for a provider
    """
    if provider not in ['openai', 'gemini', 'claude', 'perplexity']:
        return jsonify({"error": "Invalid provider"}), 400
    
    config_manager.delete_api_key(provider)
    return jsonify({"message": f"API key deleted for {provider}"})

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
