#!/usr/bin/env python3
"""
Database migration script to add new columns and update existing tables
"""

import sqlite3
import os

def migrate_database():
    db_path = '/app/data/feeds.db'  # Path inside container
    
    # Create data directory if it doesn't exist
    os.makedirs('/app/data', exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if feed_items table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feed_items'")
        if not cursor.fetchone():
            print("feed_items table doesn't exist yet, will be created on first run")
            conn.close()
            return
            
        # Add image column to feed_items if it doesn't exist
        cursor.execute("PRAGMA table_info(feed_items)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'image' not in columns:
            print("Adding image column to feed_items table...")
            cursor.execute("ALTER TABLE feed_items ADD COLUMN image TEXT")
            conn.commit()
            print("✓ Image column added successfully!")
        else:
            print("✓ Image column already exists")
        
        # Add extraction_patterns column to feeds if it doesn't exist
        cursor.execute("PRAGMA table_info(feeds)")
        feeds_columns = [column[1] for column in cursor.fetchall()]
        
        if 'extraction_patterns' not in feeds_columns:
            print("Adding extraction_patterns column to feeds table...")
            cursor.execute("ALTER TABLE feeds ADD COLUMN extraction_patterns TEXT")
            conn.commit()
            print("✓ Extraction patterns column added successfully!")
        else:
            print("✓ Extraction patterns column already exists")
            
        if 'last_ai_analysis' not in feeds_columns:
            print("Adding last_ai_analysis column to feeds table...")
            cursor.execute("ALTER TABLE feeds ADD COLUMN last_ai_analysis TIMESTAMP")
            conn.commit()
            print("✓ Last AI analysis column added successfully!")
        else:
            print("✓ Last AI analysis column already exists")
            
    except sqlite3.OperationalError as e:
        print(f"Error during migration: {e}")
    
    conn.close()

if __name__ == "__main__":
    migrate_database()