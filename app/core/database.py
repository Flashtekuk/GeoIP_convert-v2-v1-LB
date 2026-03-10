import sqlite3
import os
import logging

logger = logging.getLogger("DATABASE")

DB_PATH = "data/history.db"

def init_db():
    """Initializes the history database if it doesn't exist."""
    logger.info("Initializes the history database if it doesn't exist.")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            task_type TEXT,        -- 'Scheduled' or 'Manual'
            status TEXT,           -- 'Success', 'Failed', or 'Skipped'
            checksum TEXT,         -- The SHA-256 hash
            details TEXT           -- Error messages or server count
        )
    ''')
    conn.commit()
    conn.close()

def log_task(task_type, status, checksum, details):
    logger.info(f"Logging task to database: {task_type}, {status}, {checksum}, {details}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO task_history (task_type, status, checksum, details)
        VALUES (?, ?, ?, ?)
    ''', (task_type, status, checksum, details))
    conn.commit()
    conn.close()

def clear_entire_database():
    """Wipes all records from the main table"""
    logger.info("Wipes all records from the main table")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor() 
    cursor.execute("DELETE FROM task_history")
    conn.commit()
    conn.close()

def trim_database(limit=60):
    """
    Keeps only the most recent N records based on the ID.
    """
    logger.info("Trimming database")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = f"""
        DELETE FROM task_history
        WHERE id NOT IN (
            SELECT id FROM task_history
            ORDER BY id DESC
            LIMIT {limit}
        )
        """
    cursor.execute(query)
    conn.commit()
    conn.close()