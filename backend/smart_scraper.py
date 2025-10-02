"""
Smart Scraper - Uses saved patterns to extract content without AI
"""
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import re

class SmartScraper:
    def __init__(self):
        pass
    
    def scrape_with_patterns(self, url, patterns_json):
        """
        Scrape website using saved extraction patterns
        """
        try:
            patterns = json.loads(patterns_json)
        except:
            return {"error": "Invalid patterns"}
        
        # Fetch website content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Try to fix common HTML issues
            html_content = response.content
            
            # Fix encoding issues
            if response.encoding:
                html_content = response.text.encode('utf-8')
            
        except requests.RequestException as e:
            return {"error": f"Failed to fetch website: {str(e)}"}
        
        try:
            # Use lxml parser for better HTML handling, fallback to html.parser
            soup = BeautifulSoup(html_content, 'lxml')
        except:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
            except Exception as e:
                return {"error": f"Failed to parse HTML: {str(e)}"}
        
        # Extract articles using patterns
        articles = self._extract_articles_with_patterns(soup, patterns, url)
        
        # Build result similar to AI result
        result = {
            "title": self._extract_site_title(soup),
            "description": self._extract_site_description(soup),
            "items": articles
        }
        
        return result
    
    def _extract_articles_with_patterns(self, soup, patterns, base_url):
        """Extract articles using saved patterns"""
        articles = []
        
        # Use article patterns to find containers
        containers = self._find_containers_with_patterns(soup, patterns.get('article_patterns', []))
        
        for container in containers[:10]:  # Limit to 10 articles
            article = self._extract_single_article(container, patterns, base_url)
            if article and article.get('title'):
                articles.append(article)
        
        return articles
    
    def _find_containers_with_patterns(self, soup, article_patterns):
        """Find article containers using patterns"""
        containers = []
        
        # Try each pattern
        for pattern in article_patterns:
            tag = pattern.get('tag', 'div')
            classes = pattern.get('classes', [])
            
            if classes:
                # Find by tag and class
                found = soup.find_all(tag, class_=lambda x: x and any(
                    cls in x for cls in classes
                ))
                containers.extend(found)
            else:
                # Find by tag only
                found = soup.find_all(tag)
                containers.extend(found)
        
        # Remove duplicates
        containers = list(dict.fromkeys(containers))
        
        # Fallback to common patterns if no containers found
        if not containers:
            containers = self._fallback_container_search(soup)
        
        return containers
    
    def _fallback_container_search(self, soup):
        """Fallback search for article containers"""
        containers = []
        
        # Look for article elements
        containers.extend(soup.find_all('article'))
        
        # Look for divs with article-like classes
        article_divs = soup.find_all('div', class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['post', 'article', 'news', 'entry', 'item', 'story', 'blog']
        ))
        containers.extend(article_divs)
        
        return containers
    
    def _extract_single_article(self, container, patterns, base_url):
        """Extract single article data"""
        article = {
            'title': '',
            'link': '',
            'description': '',
            'pubDate': '',
            'image': ''
        }
        
        # Extract title
        article['title'] = self._extract_title(container, patterns)
        
        # Extract link
        article['link'] = self._extract_link(container, patterns, base_url)
        
        # Extract description
        article['description'] = self._extract_description(container, patterns)
        
        # Extract date
        article['pubDate'] = self._extract_date(container, patterns)
        
        # Extract image
        article['image'] = self._extract_image(container, patterns, base_url)
        
        return article
    
    def _extract_title(self, container, patterns):
        """Extract title from container"""
        # Try title selectors from patterns
        selectors = patterns.get('content_selectors', {}).get('title_patterns', [])
        
        for selector in selectors:
            try:
                if selector.startswith('.'):
                    # Class selector
                    elem = container.find(class_=selector[1:])
                else:
                    # Tag selector
                    elem = container.find(selector)
                
                if elem:
                    return elem.get_text().strip()
            except:
                continue
        
        # Fallback to common title patterns
        title_elem = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if title_elem:
            return title_elem.get_text().strip()
        
        return ""
    
    def _extract_link(self, container, patterns, base_url):
        """Extract article link"""
        # Find first link in container
        link_elem = container.find('a', href=True)
        if link_elem:
            href = link_elem.get('href', '')
            if href.startswith('http'):
                return href
            elif href.startswith('/'):
                return urljoin(base_url, href)
            else:
                return urljoin(base_url + '/', href)
        
        return ""
    
    def _extract_description(self, container, patterns):
        """Extract article description"""
        # Try to find excerpt or summary
        desc_elem = container.find(class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['excerpt', 'summary', 'description']
        ))
        
        if desc_elem:
            return desc_elem.get_text().strip()[:400]  # Limit to 400 chars
        
        # Fallback to all text content
        text = container.get_text().strip()
        # Remove title text if found
        lines = text.split('\n')
        if len(lines) > 1:
            return ' '.join(lines[1:])[:400]  # Skip first line (likely title)
        
        return text[:400]
    
    def _extract_date(self, container, patterns):
        """Extract publication date"""
        # Try time elements
        time_elem = container.find('time')
        if time_elem:
            datetime_attr = time_elem.get('datetime')
            if datetime_attr:
                return datetime_attr.split('T')[0]  # Return just date part
            text = time_elem.get_text().strip()
            if text:
                return self._parse_date_text(text)
        
        # Try date classes
        date_elem = container.find(class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['date', 'time', 'published', 'created']
        ))
        
        if date_elem:
            text = date_elem.get_text().strip()
            return self._parse_date_text(text)
        
        return ""
    
    def _parse_date_text(self, text):
        """Parse date from text"""
        # Simple date parsing - could be improved
        today = datetime.now()
        
        # Look for year patterns
        year_match = re.search(r'202[0-9]', text)
        if year_match:
            year = year_match.group()
            # Try to extract month and day too
            return f"{year}-01-01"  # Simplified
        
        return ""
    
    def _extract_image(self, container, patterns, base_url):
        """Extract article image using multiple comprehensive strategies"""
        
        # Strategy 1: Use saved image patterns from AI analysis
        if 'image_patterns' in patterns:
            for pattern in patterns['image_patterns']:
                if pattern.get('category') == 'featured':
                    selector = pattern.get('selector', 'img')
                    img_elem = container.select_one(selector)
                    if img_elem and img_elem.get('src'):
                        return self._normalize_url(img_elem['src'], base_url)
        
        # Strategy 2: Look for images in absolute positioned divs (common in modern sites)
        absolute_divs = container.find_all('div', class_=lambda x: x and any(
            'absolute' in ' '.join(x).lower() for x in [x] if x
        ))
        
        for div in absolute_divs:
            img = div.find('img', src=True)
            if img and img.get('src'):
                return self._normalize_url(img['src'], base_url)
        
        # Strategy 3: Look for featured/hero image patterns
        featured_selectors = [
            'img.featured-image',
            'img.hero-image', 
            'img.thumbnail',
            'img.cover-image',
            '.featured-image img',
            '.hero-image img',
            '.thumbnail img',
            '.cover img',
            '.image-wrapper img',
            '.post-image img'
        ]
        
        for selector in featured_selectors:
            img_elem = container.select_one(selector)
            if img_elem and img_elem.get('src'):
                return self._normalize_url(img_elem['src'], base_url)
        
        # Strategy 4: Look for images with specific class patterns
        featured_img = container.find('img', class_=lambda x: x and any(
            keyword in ' '.join(x).lower() for keyword in ['featured', 'thumbnail', 'cover', 'hero', 'main', 'primary']
        ))
        
        if featured_img and featured_img.get('src'):
            return self._normalize_url(featured_img['src'], base_url)
        
        # Strategy 5: Look for first significant image in any div
        for img in container.find_all('img', src=True):
            src = img.get('src', '')
            alt = img.get('alt', '').lower()
            
            # Skip small images, icons, and logos
            if any(keyword in src.lower() for keyword in ['icon', 'logo', 'avatar', 'emoji', 'spinner', 'button']):
                continue
            if any(keyword in alt for keyword in ['icon', 'logo', 'avatar', 'emoji']):
                continue
            
            # Check image dimensions if available
            width = img.get('width')
            height = img.get('height')
            if width and height:
                try:
                    w, h = int(width), int(height)
                    if w < 80 or h < 80:  # Skip very small images
                        continue
                except:
                    pass
            
            # Check if image is in a meaningful container
            parent = img.parent
            if parent:
                parent_classes = ' '.join(parent.get('class', [])).lower()
                if any(keyword in parent_classes for keyword in ['image', 'photo', 'picture', 'media', 'visual']):
                    return self._normalize_url(src, base_url)
                
                # Check for modern CSS classes like absolute positioning
                if any(keyword in parent_classes for keyword in ['absolute', 'relative', 'flex', 'grid']):
                    return self._normalize_url(src, base_url)
            
            return self._normalize_url(src, base_url)
        
        # Strategy 6: Look for background images in CSS styles
        for elem in container.find_all(style=True):
            style = elem.get('style', '')
            if 'background-image' in style:
                match = re.search(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
                if match:
                    return self._normalize_url(match.group(1), base_url)
        
        # Strategy 7: Look for data attributes that might contain image URLs
        for elem in container.find_all():
            for attr_name, attr_value in elem.attrs.items():
                if isinstance(attr_value, str) and any(keyword in attr_name.lower() for keyword in ['data-src', 'data-image', 'data-bg']):
                    if attr_value.startswith(('http', '/', '.')):
                        return self._normalize_url(attr_value, base_url)
        
        return ""
    
    def _normalize_url(self, url, base_url):
        """Normalize relative URLs to absolute"""
        if url.startswith('http'):
            return url
        elif url.startswith('/'):
            return urljoin(base_url, url)
        elif url.startswith('data:'):
            return ""  # Skip data URLs
        else:
            return urljoin(base_url + '/', url)
    
    def _extract_site_title(self, soup):
        """Extract site title"""
        title_elem = soup.find('title')
        if title_elem:
            return title_elem.get_text().strip()
        
        h1_elem = soup.find('h1')
        if h1_elem:
            return h1_elem.get_text().strip()
        
        return "Generated Feed"
    
    def _extract_site_description(self, soup):
        """Extract site description"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            return meta_desc.get('content', '')
        
        return "Auto-generated RSS feed"

def scrape_with_patterns(url, patterns_json):
    """Utility function to scrape with patterns"""
    scraper = SmartScraper()
    return scraper.scrape_with_patterns(url, patterns_json)