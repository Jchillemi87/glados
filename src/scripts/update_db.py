import sys
import os

# Path Hack
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.database import init_db, engine

def update_schema():
    print(f"--- UPDATING DATABASE SCHEMA ---")
    print(f"Target Database: {engine.url}")
    
    # This will create 'maintenance_log' without touching 'amazon_orders'
    try:
        init_db()
        print("[SUCCESS] Schema updated. New tables created if they were missing.")
    except Exception as e:
        print(f"[ERROR] Failed to update schema: {e}")

if __name__ == "__main__":
    update_schema()