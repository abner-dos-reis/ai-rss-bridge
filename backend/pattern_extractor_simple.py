"""
Simple Pattern Extractor - Backup version
"""
import json
from bs4 import BeautifulSoup

def extract_patterns(url, html_content, ai_result):
    """Simple pattern extraction"""
    try:
        patterns = {
            'base_url': '/'.join(url.split('/')[:3]),
            'site_structure': {},
            'article_patterns': ['article', 'div.post', 'div.entry'],
            'content_selectors': {
                'title_patterns': ['h1', 'h2', 'h3', '.title'],
                'description_patterns': ['.excerpt', '.summary', 'p'],
                'link_patterns': ['a[href]'],
                'image_patterns': ['img[src]', '.featured-image img']
            },
            'image_patterns': [],
            'date_patterns': [],
            'link_patterns': []
        }
        
        return json.dumps(patterns, indent=2)
    except Exception as e:
        print(f"Pattern extraction error: {e}")
        return "{}"