# src/scripts/load_finance.py
import sys
import os
import pandas as pd
from sqlalchemy.orm import Session

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(SCRIPT_DIR, "../..")))

# Ensure you are importing the updated AmazonOrder class with the new column!
from src.core.database import init_db, SessionLocal, AmazonOrder

CSV_PATH = os.path.join(SCRIPT_DIR, "amazon_orders.csv")

def clean_price(price_val):
    if pd.isna(price_val): return 0.0
    s = str(price_val).replace('$', '').replace(',', '').strip()
    try:
        return float(s)
    except:
        return 0.0

def load_csv_to_db():
    print(f"--- LOADING FINANCE DATA FROM {CSV_PATH} ---")
    
    if not os.path.exists(CSV_PATH):
        print(f"[ERROR] {CSV_PATH} not found.")
        return

    init_db()
    db: Session = SessionLocal()

    try:
        df = pd.read_csv(CSV_PATH)
        print(f"Loaded CSV with {len(df)} rows.")
    except Exception as e:
        print(f"[ERROR] Could not read CSV: {e}")
        return

    # Cache existing entries to prevent duplicates
    existing_hashes = set()
    existing = db.query(AmazonOrder.order_id, AmazonOrder.item_description).all()
    for oid, desc in existing:
        existing_hashes.add((oid, desc))

    added_count = 0
    skipped_count = 0

    for _, row in df.iterrows():
        order_id = str(row.get('Order ID', 'Unknown'))
        desc = str(row.get('Description', 'Unknown'))
        raw_date = row.get('Date', None)
        
        # Validation
        if (order_id, desc) in existing_hashes:
            skipped_count += 1
            continue

        date_obj = None
        if pd.notna(raw_date) and str(raw_date) != "Unknown":
            try:
                date_obj = pd.to_datetime(raw_date).date()
            except:
                pass 

        db_item = AmazonOrder(
            order_id=order_id,
            date=date_obj,
            # NEW: Map Account Column
            account_owner=str(row.get('Account', 'Unknown')), 
            item_description=desc,
            item_price=clean_price(row.get('Price')),
            quantity=int(row.get('Quantity', 1)),
            category=str(row.get('Category', 'Unknown')),
            link=str(row.get('Link', ''))
        )
        
        db.add(db_item)
        added_count += 1

    db.commit()
    db.close()
    
    print(f"--- SYNC COMPLETE ---")
    print(f"Added:   {added_count}")
    print(f"Skipped: {skipped_count}")

if __name__ == "__main__":
    load_csv_to_db()