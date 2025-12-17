import sys
import os
import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime

# Path Hack to find 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.database import init_db, SessionLocal, AmazonOrder

CSV_PATH = "amazon_orders.csv"

def clean_price(price_val):
    """Converts '$1,234.56' -> 1234.56"""
    if pd.isna(price_val): return 0.0
    s = str(price_val).replace('$', '').replace(',', '').strip()
    try:
        return float(s)
    except:
        return 0.0

def load_csv_to_db():
    print(f"--- LOADING FINANCE DATA FROM {CSV_PATH} ---")
    
    if not os.path.exists(CSV_PATH):
        print(f"[ERROR] {CSV_PATH} not found. Run ingest_amazon.py first.")
        return

    # 1. Initialize DB
    init_db()
    db: Session = SessionLocal()

    # 2. Read CSV
    try:
        df = pd.read_csv(CSV_PATH)
        print(f"Loaded CSV with {len(df)} rows.")
    except Exception as e:
        print(f"[ERROR] Could not read CSV: {e}")
        return

    # 3. Clean Data & Deduplicate
    # We fetch existing IDs to avoid duplicates if you run this script twice
    existing_hashes = set()
    existing = db.query(AmazonOrder.order_id, AmazonOrder.item_description).all()
    for oid, desc in existing:
        existing_hashes.add((oid, desc))

    added_count = 0
    skipped_count = 0

    for _, row in df.iterrows():
        # Schema Mapping
        order_id = str(row.get('Order ID', 'Unknown'))
        desc = str(row.get('Description', 'Unknown'))
        raw_date = row.get('Date', None)
        
        # Validation
        if (order_id, desc) in existing_hashes:
            skipped_count += 1
            continue

        # Parse Date (Handle various formats or NaT)
        date_obj = None
        if pd.notna(raw_date) and str(raw_date) != "Unknown":
            try:
                date_obj = pd.to_datetime(raw_date).date()
            except:
                pass # Leave as None if parse fails

        # Create Record
        db_item = AmazonOrder(
            order_id=order_id,
            date=date_obj,
            item_description=desc,
            item_price=clean_price(row.get('Price')),
            quantity=int(row.get('Quantity', 1)),
            category=str(row.get('Category', 'Unknown')),
            link=str(row.get('Link', ''))
        )
        
        db.add(db_item)
        added_count += 1

    # 4. Commit
    db.commit()
    db.close()
    
    print(f"--- SYNC COMPLETE ---")
    print(f"Added:   {added_count}")
    print(f"Skipped: {skipped_count} (Duplicates)")
    print(f"Total:   {len(df)}")

if __name__ == "__main__":
    load_csv_to_db()