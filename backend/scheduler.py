import time
import threading
from datetime import datetime, timedelta
import schedule
import os
import json
from database import DatabaseManager
from ai_providers import get_ai_provider
import requests
from bs4 import BeautifulSoup

class FeedScheduler:
    def __init__(self, db_manager):
        self.db = db_manager
        self.running = False
        self.scheduler_thread = None
        self.api_keys = {}  # Store API keys temporarily for auto-updates
        
    def set_api_key(self, provider, api_key):
        """Set API key for a provider for auto-updates"""
        self.api_keys[provider] = api_key
        
    def start_scheduler(self):
        """Start the background scheduler"""
        if not self.running:
            self.running = True
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            print("Feed scheduler started")
            
    def stop_scheduler(self):
        """Stop the background scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join()
        print("Feed scheduler stopped")
        
    def _run_scheduler(self):
        """Run the scheduler loop"""
        # Schedule automatic updates every hour
        schedule.every(1).hours.do(self._update_all_feeds)
        
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
            
    def _update_all_feeds(self):
        """Update all feeds that have API keys available"""
        print(f"[{datetime.now()}] Running automatic feed updates...")
        
        feeds = self.db.get_all_feeds()
        updated_count = 0
        
        for feed in feeds:
            provider = feed['ai_provider']
            if provider in self.api_keys:
                try:
                    success = self._update_single_feed(feed, self.api_keys[provider])
                    if success:
                        updated_count += 1
                        print(f"Updated feed: {feed['title']}")
                    else:
                        print(f"Failed to update feed: {feed['title']}")
                except Exception as e:
                    print(f"Error updating feed {feed['title']}: {str(e)}")
                    
                # Add delay between requests to be respectful
                time.sleep(2)
        
        print(f"Automatic update completed. Updated {updated_count} feeds.")
        
    def _update_single_feed(self, feed, api_key):
        """Update a single feed with fresh content"""
        try:
            # Fetch fresh content
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(feed['url'], headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            html_content = soup.get_text()
            
            # Extract with AI
            provider = get_ai_provider(feed['ai_provider'], api_key)
            ai_result = provider.extract_content(feed['url'], html_content)
            
            if "error" in ai_result:
                return False
            
            # Update database
            self.db.save_feed(
                url=feed['url'],
                title=ai_result.get('title', feed['title']),
                description=ai_result.get('description', feed['description']),
                ai_provider=feed['ai_provider'],
                items=ai_result.get('items', [])
            )
            
            return True
            
        except Exception as e:
            print(f"Update error for {feed['url']}: {str(e)}")
            return False
            
    def update_feed_manually(self, feed_id, api_key):
        """Manually update a specific feed"""
        feeds = self.db.get_all_feeds()
        feed_info = None
        for feed in feeds:
            if feed['id'] == feed_id:
                feed_info = feed
                break
                
        if not feed_info:
            return False, "Feed not found"
            
        success = self._update_single_feed(feed_info, api_key)
        return success, "Update completed" if success else "Update failed"

# Global scheduler instance
scheduler = None

def get_scheduler(db_manager):
    """Get or create the global scheduler instance"""
    global scheduler
    if scheduler is None:
        scheduler = FeedScheduler(db_manager)
    return scheduler