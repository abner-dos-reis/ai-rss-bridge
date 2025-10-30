import sqlite3
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="feeds.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create feeds table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                description TEXT,
                ai_provider TEXT,
                extraction_patterns TEXT,
                last_ai_analysis TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                update_interval INTEGER DEFAULT 3600
            )
        ''')
        
        # Create feed_items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feed_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER,
                title TEXT,
                link TEXT,
                description TEXT,
                pub_date TEXT,
                image TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (feed_id) REFERENCES feeds (id)
            )
        ''')
        
        # Create site_sessions table for login credentials
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS site_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_url TEXT UNIQUE NOT NULL,
                site_name TEXT,
                cookies TEXT,
                headers TEXT,
                session_data TEXT,
                logged_in BOOLEAN DEFAULT 1,
                last_validated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create cache table for website content
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                content TEXT,
                status_code INTEGER,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_feed(self, url, title, description, ai_provider, items, extraction_patterns=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert or update feed
        cursor.execute('''
            INSERT OR REPLACE INTO feeds (url, title, description, ai_provider, extraction_patterns, last_ai_analysis, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (url, title, description, ai_provider, extraction_patterns, datetime.now(), datetime.now()))
        
        feed_id = cursor.lastrowid
        if not feed_id:
            cursor.execute('SELECT id FROM feeds WHERE url = ?', (url,))
            feed_id = cursor.fetchone()[0]
        
        # Clear old items
        cursor.execute('DELETE FROM feed_items WHERE feed_id = ?', (feed_id,))
        
        # Insert new items
        for item in items:
            cursor.execute('''
                INSERT INTO feed_items (feed_id, title, link, description, pub_date, image)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (feed_id, item.get('title'), item.get('link'), 
                  item.get('description'), item.get('pubDate'), item.get('image')))
        
        conn.commit()
        conn.close()
        return feed_id
    
    def get_all_feeds(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, url, title, description, ai_provider, extraction_patterns, last_ai_analysis, created_at, updated_at
            FROM feeds ORDER BY updated_at DESC
        ''')
        
        feeds = []
        for row in cursor.fetchall():
            feeds.append({
                'id': row[0],
                'url': row[1],
                'title': row[2],
                'description': row[3],
                'ai_provider': row[4],
                'extraction_patterns': row[5],
                'last_ai_analysis': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            })
        
        conn.close()
        return feeds
    
    def get_feed_items(self, feed_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT title, link, description, pub_date, image
            FROM feed_items WHERE feed_id = ?
            ORDER BY created_at DESC
        ''', (feed_id,))
        
        items = []
        for row in cursor.fetchall():
            items.append({
                'title': row[0],
                'link': row[1],
                'description': row[2],
                'pubDate': row[3],
                'image': row[4]
            })
        
        conn.close()
        return items
    
    def get_feed_by_url(self, url):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM feeds WHERE url = ?', (url,))
        row = cursor.fetchone()
        
        if row:
            feed = {
                'id': row[0],
                'url': row[1],
                'title': row[2],
                'description': row[3],
                'ai_provider': row[4],
                'created_at': row[5],
                'updated_at': row[6],
                'update_interval': row[7]
            }
            conn.close()
            return feed
        
        conn.close()
        return None
    
    def get_feed_by_id(self, feed_id):
        """Get a specific feed by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM feeds WHERE id = ?', (feed_id,))
        row = cursor.fetchone()
        
        if row:
            feed = {
                'id': row[0],
                'url': row[1],
                'title': row[2],
                'description': row[3],
                'ai_provider': row[4],
                'extraction_patterns': row[5],
                'last_ai_analysis': row[6],
                'created_at': row[7],
                'updated_at': row[8],
                'update_interval': row[9]
            }
            conn.close()
            return feed
        
        conn.close()
        return None
    
    def update_feed(self, feed_id, title, description, ai_provider, items):
        """Update an existing feed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Update feed info
        cursor.execute('''
            UPDATE feeds 
            SET title = ?, description = ?, ai_provider = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (title, description, ai_provider, feed_id))
        
        # Delete old items and insert new ones
        cursor.execute('DELETE FROM feed_items WHERE feed_id = ?', (feed_id,))
        
        for item in items:
            cursor.execute('''
                INSERT INTO feed_items (feed_id, title, link, description, pub_date, image)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                feed_id,
                item.get('title', ''),
                item.get('link', ''),
                item.get('description', ''),
                item.get('pubDate', ''),
                item.get('image', '')
            ))
        
        conn.commit()
        conn.close()
        return feed_id
    
    def delete_feed(self, feed_id):
        """Delete a feed and all its items"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Delete feed items first (foreign key constraint)
        cursor.execute('DELETE FROM feed_items WHERE feed_id = ?', (feed_id,))
        # Delete the feed
        cursor.execute('DELETE FROM feeds WHERE id = ?', (feed_id,))
        
        # Check if there are no more feeds and reset sequence if needed
        cursor.execute('SELECT COUNT(*) FROM feeds')
        count = cursor.fetchone()[0]
        if count == 0:
            # Reset the autoincrement sequence
            cursor.execute('DELETE FROM sqlite_sequence WHERE name = "feeds"')
        
        conn.commit()
        conn.close()
    
    def delete_all_feeds(self):
        """Delete all feeds and items"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Delete all feed items first
        cursor.execute('DELETE FROM feed_items')
        # Delete all feeds
        cursor.execute('DELETE FROM feeds')
        
        # Reset the autoincrement sequence to start from 1 again
        cursor.execute('DELETE FROM sqlite_sequence WHERE name = "feeds"')
        cursor.execute('DELETE FROM sqlite_sequence WHERE name = "feed_items"')
        
        conn.commit()
        conn.close()
    
    # Site Session Management
    def save_site_session(self, site_url, site_name, cookies, headers=None, session_data=None):
        """Save login session for a website"""
        import json
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO site_sessions 
            (site_url, site_name, cookies, headers, session_data, logged_in, last_validated, created_at)
            VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, 
                    COALESCE((SELECT created_at FROM site_sessions WHERE site_url = ?), CURRENT_TIMESTAMP))
        ''', (
            site_url,
            site_name,
            json.dumps(cookies) if cookies else None,
            json.dumps(headers) if headers else None,
            json.dumps(session_data) if session_data else None,
            site_url
        ))
        
        conn.commit()
        conn.close()
    
    def get_site_session(self, site_url):
        """Get login session for a website"""
        import json
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, site_url, site_name, cookies, headers, session_data, logged_in, last_validated, created_at
            FROM site_sessions WHERE site_url = ?
        ''', (site_url,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'site_url': row[1],
                'site_name': row[2],
                'cookies': json.loads(row[3]) if row[3] else None,
                'headers': json.loads(row[4]) if row[4] else None,
                'session_data': json.loads(row[5]) if row[5] else None,
                'logged_in': bool(row[6]),
                'last_validated': row[7],
                'created_at': row[8]
            }
        return None
    
    def get_all_site_sessions(self):
        """Get all site sessions"""
        import json
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, site_url, site_name, logged_in, last_validated, created_at
            FROM site_sessions ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'site_url': row[1],
            'site_name': row[2],
            'logged_in': bool(row[3]),
            'last_validated': row[4],
            'created_at': row[5]
        } for row in rows]
    
    def delete_site_session(self, site_url):
        """Delete login session for a website"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM site_sessions WHERE site_url = ?', (site_url,))
        
        conn.commit()
        conn.close()
    
    def mark_session_logged_out(self, site_url):
        """Mark a session as logged out"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE site_sessions SET logged_in = 0, last_validated = CURRENT_TIMESTAMP
            WHERE site_url = ?
        ''', (site_url,))
        
        conn.commit()
        conn.close()
    
    # Content Cache Management
    def get_cached_content(self, url):
        """Get cached content if not expired"""
        from datetime import datetime
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT content, status_code, cached_at, expires_at
            FROM content_cache 
            WHERE url = ? AND expires_at > CURRENT_TIMESTAMP
        ''', (url,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'content': row[0],
                'status_code': row[1],
                'cached_at': row[2],
                'expires_at': row[3]
            }
        return None
    
    def save_cached_content(self, url, content, status_code, cache_hours=24):
        """Save content to cache with expiration"""
        from datetime import datetime, timedelta
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        expires_at = datetime.now() + timedelta(hours=cache_hours)
        
        cursor.execute('''
            INSERT OR REPLACE INTO content_cache (url, content, status_code, cached_at, expires_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (url, content, status_code, expires_at.strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        conn.close()
    
    def clear_expired_cache(self):
        """Remove expired cache entries"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM content_cache WHERE expires_at <= CURRENT_TIMESTAMP')
        
        conn.commit()
        conn.close()
    
    def clear_cache_for_url(self, url):
        """Clear cache for specific URL"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM content_cache WHERE url = ?', (url,))
        
        conn.commit()
        conn.close()