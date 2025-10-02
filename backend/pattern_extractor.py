"""
Pattern Extractor - Analyzes HTML content and creates reusable extraction patterns
"""
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

class PatternExtractor:
    def __init__(self):
        pass
    
    def analyze_html_patterns(self, url, html_content, ai_result):
        """
        Analyze HTML content and AI result to extract reusable patterns
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        patterns = {
            'base_url': '/'.join(url.split('/')[:3]),
            'site_structure': {},
            'article_patterns': [],
            'content_selectors': {},
            'image_patterns': [],
            'date_patterns': [],
            'link_patterns': []
        }
        
        # Analyze article containers
        article_containers = self._find_article_containers(soup)
        patterns['article_patterns'] = self._extract_article_patterns(article_containers)
        
        # Analyze content structure based on AI results
        if ai_result.get('items'):
            patterns['content_selectors'] = self._analyze_content_selectors(soup, ai_result['items'])
        
        # Extract image patterns
        patterns['image_patterns'] = self._extract_image_patterns(soup)
        
        # Extract date patterns
        patterns['date_patterns'] = self._extract_date_patterns(soup)
        
        # Extract link patterns
        patterns['link_patterns'] = self._extract_link_patterns(soup, url)
        
        return json.dumps(patterns, indent=2)
    
    def _find_article_containers(self, soup):
        """Find common article containers"""
        containers = []
        
        # Look for article elements
        articles = soup.find_all('article')
        containers.extend(articles)
        
        # Look for divs with article-like classes
        article_divs = soup.find_all('div', class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['post', 'article', 'news', 'entry', 'item', 'story', 'blog']
        ))
        containers.extend(article_divs)
        
        # Look for list items that might be articles
        li_articles = soup.find_all('li', class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['post', 'article', 'news', 'entry', 'item']
        ))
        containers.extend(li_articles)
        
        return containers[:15]  # Limit to first 15
    
    def _extract_article_patterns(self, containers):
        """Extract patterns from article containers"""
        patterns = []
        
        for container in containers:
            pattern = {
                'tag': container.name,
                'classes': container.get('class', []),
                'title_selectors': [],
                'link_selectors': [],
                'image_selectors': [],
                'date_selectors': [],
                'content_selectors': []
            }
            
            # Find title patterns
            title_elements = container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for title in title_elements:
                pattern['title_selectors'].append({
                    'tag': title.name,
                    'classes': title.get('class', [])
                })
            
            # Find link patterns
            links = container.find_all('a', href=True)
            for link in links:
                pattern['link_selectors'].append({
                    'tag': link.name,
                    'classes': link.get('class', []),
                    'href_pattern': link.get('href', '')
                })
            
            # Find image patterns
            images = container.find_all('img', src=True)
            for img in images:
                pattern['image_selectors'].append({
                    'tag': img.name,
                    'classes': img.get('class', []),
                    'src_pattern': img.get('src', '')
                })
            
            patterns.append(pattern)
        
        return patterns
    
    def _analyze_content_selectors(self, soup, ai_items):
        """Analyze content selectors based on AI results"""
        selectors = {
            'title_patterns': [],
            'description_patterns': [],
            'link_patterns': [],
            'image_patterns': []
        }
        
        # This would be more sophisticated in production
        # For now, we'll use common patterns
        selectors['title_patterns'] = ['h1', 'h2', 'h3', '.title', '.headline', '.post-title']
        selectors['description_patterns'] = ['.excerpt', '.summary', '.description', 'p']
        selectors['link_patterns'] = ['a[href]']
        selectors['image_patterns'] = ['img[src]', '.featured-image img', '.post-image img']
        
        return selectors
    
    def _extract_image_patterns(self, soup):
        """Extract comprehensive image URL patterns from modern websites"""
        patterns = []
        
        # Find all images with various selection strategies
        all_images = soup.find_all('img', src=True)
        
        # Strategy 1: Images in absolute positioned containers (modern design)
        absolute_containers = soup.find_all('div', class_=lambda x: x and any(
            'absolute' in ' '.join(x).lower() for x in [x] if x
        ))
        
        absolute_images = []
        for container in absolute_containers:
            imgs = container.find_all('img', src=True)
            absolute_images.extend(imgs)
        
        # Strategy 2: Featured/hero images
        featured_images = soup.find_all('img', class_=lambda x: x and any(
            keyword in ' '.join(x).lower() for keyword in ['featured', 'thumbnail', 'cover', 'hero', 'main', 'primary']
        ))
        
        # Strategy 3: Images in content/article containers
        content_images = soup.find_all('img', class_=lambda x: x and any(
            keyword in ' '.join(x).lower() for keyword in ['content', 'article', 'post', 'story']
        ))
        
        # Analyze each category with priority
        categories = [
            ('absolute', absolute_images[:3]),
            ('featured', featured_images[:3]),
            ('content', content_images[:3]),
            ('general', all_images[:3])
        ]
        
        for category, images in categories:
            for img in images:
                src = img.get('src', '')
                alt = img.get('alt', '')
                
                # Skip small/icon images
                if any(keyword in src.lower() for keyword in ['icon', 'logo', 'avatar', 'emoji', 'spinner']):
                    continue
                if any(keyword in alt.lower() for keyword in ['icon', 'logo', 'avatar', 'emoji']):
                    continue
                
                # Analyze parent container
                parent_info = self._analyze_image_parent(img)
                
                pattern = {
                    'category': category,
                    'classes': img.get('class', []),
                    'src_type': 'absolute' if src.startswith('http') else 'relative',
                    'src_pattern': src,
                    'alt_pattern': alt,
                    'parent_classes': parent_info['classes'],
                    'parent_has_absolute': parent_info['has_absolute'],
                    'selector': self._generate_comprehensive_selector(img, parent_info),
                    'priority': self._calculate_image_priority(img, parent_info, category)
                }
                patterns.append(pattern)
        
        # Sort by priority (higher is better)
        patterns.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        return patterns[:10]  # Return top 10 patterns
    
    def _analyze_image_parent(self, img):
        """Analyze image parent container for better context"""
        parent_info = {
            'classes': [],
            'has_absolute': False,
            'has_wrapper': False
        }
        
        if img.parent:
            parent_classes = img.parent.get('class', [])
            parent_info['classes'] = parent_classes
            
            parent_class_str = ' '.join(parent_classes).lower()
            parent_info['has_absolute'] = 'absolute' in parent_class_str
            parent_info['has_wrapper'] = any(keyword in parent_class_str for keyword in 
                ['wrapper', 'container', 'image', 'media', 'visual'])
        
        return parent_info
    
    def _calculate_image_priority(self, img, parent_info, category):
        """Calculate priority score for image selection"""
        priority = 0
        
        # Category priorities
        category_scores = {
            'featured': 100,
            'absolute': 90,
            'content': 70,
            'general': 50
        }
        priority += category_scores.get(category, 0)
        
        # Class-based scoring
        img_classes = ' '.join(img.get('class', [])).lower()
        if any(keyword in img_classes for keyword in ['featured', 'hero', 'main']):
            priority += 50
        if any(keyword in img_classes for keyword in ['thumbnail', 'cover']):
            priority += 30
        
        # Parent-based scoring
        if parent_info['has_absolute']:
            priority += 40
        if parent_info['has_wrapper']:
            priority += 20
        
        # Size hints (if available)
        width = img.get('width')
        height = img.get('height')
        if width and height:
            try:
                w, h = int(width), int(height)
                if w >= 200 and h >= 200:
                    priority += 30
                elif w >= 100 and h >= 100:
                    priority += 10
            except:
                pass
        
        return priority
    
    def _generate_comprehensive_selector(self, img, parent_info):
        """Generate comprehensive CSS selector for image"""
        selectors = []
        
        # Absolute container selector (modern sites)
        if parent_info['has_absolute']:
            parent_classes = '.'.join(parent_info['classes'])
            selectors.append(f'.{parent_classes} img')
        
        # Class-based selector
        if img.get('class'):
            class_selector = '.' + '.'.join(img['class'])
            selectors.append(f'img{class_selector}')
        
        # Parent wrapper selector
        if parent_info['has_wrapper']:
            parent_classes = '.'.join(parent_info['classes'])
            selectors.append(f'.{parent_classes} img')
        
        # Fallback to tag
        selectors.append('img')
        
        return selectors[0] if selectors else 'img'

    def _generate_image_selector(self, img):
        """Generate CSS selector for image"""
        selectors = []
        
        # Class-based selector
        if img.get('class'):
            class_selector = '.' + '.'.join(img['class'])
            selectors.append(f'img{class_selector}')
        
        # Parent-based selector
        if img.parent and img.parent.get('class'):
            parent_classes = '.'.join(img.parent['class'])
            selectors.append(f'.{parent_classes} img')
        
        # Fallback to tag
        selectors.append('img')
        
        return selectors[0] if selectors else 'img'
    
    def _extract_date_patterns(self, soup):
        """Extract date patterns"""
        patterns = []
        
        # Look for time elements
        time_elements = soup.find_all('time')
        for time_elem in time_elements:
            patterns.append({
                'tag': 'time',
                'classes': time_elem.get('class', []),
                'datetime_attr': time_elem.get('datetime', '')
            })
        
        # Look for date classes
        date_elements = soup.find_all(class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['date', 'time', 'published', 'created']
        ))
        for date_elem in date_elements:
            patterns.append({
                'tag': date_elem.name,
                'classes': date_elem.get('class', [])
            })
        
        return patterns
    
    def _extract_link_patterns(self, soup, base_url):
        """Extract link patterns"""
        patterns = []
        links = soup.find_all('a', href=True)
        
        for link in links[:20]:  # Analyze first 20 links
            href = link.get('href', '')
            pattern = {
                'classes': link.get('class', []),
                'href_type': 'absolute' if href.startswith('http') else 'relative',
                'href_pattern': href
            }
            patterns.append(pattern)
        
        return patterns

def extract_patterns(url, html_content, ai_result):
    """Utility function to extract patterns"""
    extractor = PatternExtractor()
    return extractor.analyze_html_patterns(url, html_content, ai_result)