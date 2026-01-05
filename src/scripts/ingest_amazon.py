# src/scripts/ingest_amazon.py
import os
import sys
import json
import asyncio
import re
import random
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import pandas as pd

# --- PATH SETUP ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(SCRIPT_DIR, "../..")))

# --- CONFIGURATION ---
# Define your two accounts here. The 'dir' will be created automatically.
ACCOUNTS = [
    {"name": "Husband", "dir": "amazon_profile_husband"},
    {"name": "Wife",   "dir": "amazon_profile_wife"}
]

OUTPUT_JSON = os.path.join(SCRIPT_DIR, "amazon_orders.json")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "amazon_orders.csv")

MAX_CONCURRENCY = 3  # Reduced slightly to be safer with multiple contexts

def clean_price(text):
    if not text: return "0.00"
    match = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text)
    if match:
        return match.group(1).replace(',', '')
    return "0.00"

def clean_date(text):
    if not text or text == "Unknown": return "Unknown"
    text = re.sub(r"(Ordered on|Digital Order:)\s*", "", text, flags=re.IGNORECASE)
    text = text.split('|')[0].strip()
    try:
        dt = datetime.strptime(text, "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        try:
            dt = datetime.strptime(text, "%b %d, %Y")
            return dt.strftime("%Y-%m-%d")
        except:
            return text

async def fetch_order_html(page, url):
    try:
        # Added realistic user-agent waiting
        await asyncio.sleep(random.uniform(0.5, 1.5)) 
        html = await page.evaluate(f"""
            async () => {{
                try {{
                    const response = await fetch('{url}');
                    return await response.text();
                }} catch (e) {{ return null; }}
            }}
        """)
        return html
    except Exception:
        return None

def parse_order_page(html, order_id, account_name):
    """
    Extracts details and tags them with the account name.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = []
    
    # 1. EXTRACT DATE
    date_str = "Unknown"
    date_comp = soup.select_one('div[data-component="orderDate"]')
    if date_comp:
        raw_text = date_comp.get_text(strip=True)
        date_match = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", raw_text)
        if date_match: date_str = clean_date(date_match.group(1))

    if date_str == "Unknown":
        date_tag = soup.select_one('.order-date-invoice-item')
        if date_tag: date_str = clean_date(date_tag.get_text(strip=True))

    if date_str == "Unknown":
        digital_date = soup.find(string=re.compile("Digital Order:"))
        if digital_date: date_str = clean_date(digital_date)

    # 2. EXTRACT TOTAL
    total = "0.00"
    total_tag = soup.find(string=re.compile("Grand Total"))
    if total_tag:
        parent = total_tag.find_parent("div") or total_tag.parent.parent
        total = clean_price(parent.get_text())

    # 3. EXTRACT ITEMS (Physical)
    title_components = soup.select('div[data-component="itemTitle"]')
    for title_div in title_components:
        try:
            link = title_div.find("a")
            description = link.get_text(strip=True) if link else title_div.get_text(strip=True)
            href = link.get("href") if link else ""
            
            card = title_div.find_parent("div", class_="a-fixed-left-grid") or title_div.parent.parent
            price_comp = card.select_one('div[data-component="unitPrice"]')
            price = clean_price(price_comp.get_text()) if price_comp else "0.00"
            
            qty = 1
            qty_div = card.select_one('.od-item-view-qty')
            if qty_div:
                qty_match = re.search(r"(\d+)", qty_div.get_text())
                if qty_match: qty = int(qty_match.group(1))

            items.append({
                "description": description,
                "price": price,
                "quantity": qty,
                "category": "Physical",
                "link": href,
                "account": account_name # TAGGING
            })
        except: continue

    # 3b. EXTRACT ITEMS (Digital)
    if not items:
        digital_rows = soup.select("#digitalOrderSummaryContainer tr")
        for row in digital_rows:
            link = row.find("a")
            if link and len(link.get_text()) > 5:
                row_text = row.get_text()
                price = clean_price(row_text) if "$" in row_text else total
                items.append({
                    "description": link.get_text(strip=True),
                    "price": price,
                    "quantity": 1,
                    "category": "Digital",
                    "link": link.get("href"),
                    "account": account_name # TAGGING
                })

    return {
        "id": order_id,
        "date": date_str,
        "total": total,
        "account": account_name,
        "items": items
    }

async def worker(name, queue, page, results, existing_ids, account_name):
    while True:
        order_meta = await queue.get()
        if order_meta is None: break

        # Unique check now includes account to be safe, though IDs are globally unique
        if order_meta['id'] in existing_ids:
            queue.task_done()
            continue

        print(f"[{name} - {account_name}] Fetching {order_meta['id']}...")
        await asyncio.sleep(random.uniform(2.0, 5.0)) # Politeness delay

        html = await fetch_order_html(page, order_meta['url'])
        
        if html:
            data = parse_order_page(html, order_meta['id'], account_name)
            
            # Metadata Date Fallback
            if data['date'] == "Unknown" and order_meta['date'] != "Unknown":
                data['date'] = clean_date(order_meta['date'])
            
            results.append(data)
            
            item_summary = f"{data['items'][0]['description'][:20]}..." if data['items'] else "No items"
            print(f"   + Saved: {data['date']} | ${data['total']} | {item_summary}")
        else:
            print(f"   [Error] Failed to fetch {order_meta['id']}")

        queue.task_done()

async def process_account(account, p, existing_data):
    """
    Runs the scraping flow for a single account profile.
    """
    existing_ids = set(item['id'] for item in existing_data)
    user_data_path = os.path.join(SCRIPT_DIR, account['dir'])
    
    print(f"\n=== PROCESSING ACCOUNT: {account['name']} ===")
    print(f"Profile Path: {user_data_path}")

    # Launch Context for this specific user
    context = await p.chromium.launch_persistent_context(
        user_data_dir=user_data_path,
        headless=False,
        viewport={"width": 1280, "height": 720},
    )
    page = await context.new_page()

    # 1. Get Years
    print(f"[{account['name']}] Checking years...")
    await page.goto("https://www.amazon.com/your-orders/orders?timeFilter=year-2025")
    
    try:
        await page.wait_for_selector("#time-filter", timeout=5000)
    except:
        print(f"!!! [{account['name']}] PLEASE LOG IN NOW !!!")
        print("Waiting 5 minutes for login completion...")
        await page.wait_for_selector("#time-filter", timeout=300000)

    years = await page.evaluate("""
        () => {
            const select = document.querySelector('#time-filter');
            return Array.from(select.options)
                .map(o => o.value)
                .filter(v => v.startsWith('year-'));
        }
    """)
    
    # 2. Harvest URLs
    account_metas = []
    
    for year_val in years:
        print(f"[{account['name']}] Scanning {year_val}...")
        await page.goto(f"https://www.amazon.com/your-orders/orders?timeFilter={year_val}")
        
        while True:
            # Grab Order Links & List-Page Dates
            metas = await page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('.js-order-card')).map(row => {
                        const link = row.querySelector("a[href*='order-details']");
                        const id = row.innerText.match(/\\d{3}-\\d{7}-\\d{7}/)?.[0] || 'Unknown';
                        
                        let date = 'Unknown';
                        const labels = Array.from(row.querySelectorAll('span'));
                        const dateLabel = labels.find(s => s.innerText.trim().toUpperCase() === 'ORDER PLACED');
                        if (dateLabel) {
                            const parentRow = dateLabel.closest('.a-row');
                            if (parentRow && parentRow.nextElementSibling) {
                                date = parentRow.nextElementSibling.innerText.trim();
                            }
                        }
                        return { url: link ? link.href : null, id: id, date: date };
                    });
                }
            """)
            
            for m in metas:
                if m['id'] != 'Unknown' and m['id'] not in existing_ids:
                    account_metas.append(m)
            
            next_btn = page.locator(".a-last a")
            if await next_btn.count() > 0:
                await next_btn.click()
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(1.5)
            else:
                break
    
    unique_metas = {m['id']: m for m in account_metas}.values()
    print(f"[{account['name']}] New orders found: {len(unique_metas)}")

    # 3. Process Details
    new_results = []
    if unique_metas:
        queue = asyncio.Queue()
        for m in unique_metas: queue.put_nowait(m)

        tasks = [asyncio.create_task(worker(f"W-{i}", queue, page, new_results, existing_ids, account['name'])) 
                 for i in range(MAX_CONCURRENCY)]
        
        await queue.join()
        for _ in range(MAX_CONCURRENCY): queue.put_nowait(None)
        await asyncio.gather(*tasks)

    await context.close()
    return new_results

async def main():
    print("--- AMAZON INGESTION v11 (Multi-Account) ---")
    
    # Load Unified JSON
    existing_data = []
    if os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, "r") as f:
                existing_data = json.load(f)
            print(f"Loaded {len(existing_data)} total orders from history.")
        except:
            print("Starting fresh DB.")

    async with async_playwright() as p:
        # Loop through accounts sequentially
        for account in ACCOUNTS:
            try:
                account_results = await process_account(account, p, existing_data)
                existing_data.extend(account_results)
            except Exception as e:
                print(f"CRITICAL ERROR processing {account['name']}: {e}")

    # Save Unified JSON
    with open(OUTPUT_JSON, "w") as f:
        json.dump(existing_data, f, indent=2)
    print(f"Updated JSON saved to {OUTPUT_JSON}")

    # Export Unified CSV
    print("Exporting to CSV...")
    csv_rows = []
    for order in existing_data:
        # Default to 'Unknown' if old data doesn't have account field
        acct = order.get('account', 'Unknown')
        
        if not order['items']:
             csv_rows.append({
                "Date": order['date'],
                "Order ID": order['id'],
                "Account": acct,
                "Description": "Unknown / Parse Failed",
                "Price": order['total'],
                "Quantity": 1,
                "Category": "Unknown",
                "Link": f"https://amazon.com/dp/your-account/order-details?orderID={order['id']}"
            })
        else:
            for item in order['items']:
                csv_rows.append({
                    "Date": order['date'],
                    "Order ID": order['id'],
                    "Account": acct,
                    "Description": item['description'],
                    "Price": item['price'],
                    "Quantity": item['quantity'],
                    "Category": item['category'],
                    "Link": f"https://amazon.com{item.get('link', '')}"
                })
    
    df = pd.DataFrame(csv_rows)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.sort_values(by='Date', ascending=False)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"CSV saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    asyncio.run(main())