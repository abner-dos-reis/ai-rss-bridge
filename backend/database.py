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