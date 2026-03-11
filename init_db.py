"""
Database initialization script.

Run this script to create all database tables.
"""

from storage.database import init_db

if __name__ == "__main__":
    init_db()
