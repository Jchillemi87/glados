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
# 1. Identify where this script file is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Append project root to sys.path for imports (Keep this as is)
sys.path.append(os.path.abspath(os.path.join(SCRIPT_DIR, "../..")))
from src.core.config import settings

# 3. Define output paths relative to SCRIPT_DIR, not os.getcwd()
USER_DATA_DIR = os.path.join(SCRIPT_DIR, "amazon_browser_profile")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "amazon_orders.json")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "amazon_orders.csv")

MAX_CONCURRENCY = 4

def clean_price(text):
    if not text: return "0.00"
    match = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text)
    if match:
        return match.group(1).replace(',', '')
    return "0.00"

def clean_date(text):
    """
    Parses 'Ordered on January 1, 2025' or 'December 9, 2025' -> '2025-01-01'
    """
    if not text or text == "Unknown": return "Unknown"
    
    # 1. Clean noise
    # Remove "Ordered on", "Digital Order:", and trailing separator bars like "|"
    text = re.sub(r"(Ordered on|Digital Order:)\s*", "", text, flags=re.IGNORECASE)
    text = text.split('|')[0].strip() # Remove " | Order # 123..." if present
    
    # 2. Try parsing
    try:
        # Standard format: "December 9, 2025"
        dt = datetime.strptime(text, "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        try:
            # Alternate: "Dec 9, 2025"
            dt = datetime.strptime(text, "%b %d, %Y")
            return dt.strftime("%Y-%m-%d")
        except:
            return text # Return raw if parse fails

async def fetch_order_html(page, url):
    try:
        html = await page.evaluate(f"""
            async () => {{
                try {{
                    const response = await fetch('{url}');
                    return await response.text();
                }} catch (e) {{
                    return null;
                }}
            }}
        """)
        return html
    except Exception:
        return None

def parse_order_page(html, order_id):
    """
    Extracts details from the HTML of a specific Order Details page.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = []
    
    # --- 1. EXTRACT DATE (Fixed for 2025 Layout) ---
    date_str = "Unknown"
    
    # Strategy A: New 2025 data-component (From your snippet)
    # <div data-component="orderDate"> ... <span>December 9, 2025</span> ... </div>
    date_comp = soup.select_one('div[data-component="orderDate"]')
    if date_comp:
        # It usually has a nested span, or we just grab text and regex it
        raw_text = date_comp.get_text(strip=True)
        # Regex to find "Month DD, YYYY" pattern inside the messy text
        date_match = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", raw_text)
        if date_match:
            date_str = clean_date(date_match.group(1))

    # Strategy B: Fallback to old class
    if date_str == "Unknown":
        date_tag = soup.select_one('.order-date-invoice-item')
        if date_tag:
            date_str = clean_date(date_tag.get_text(strip=True))

    # Strategy C: Digital Orders header
    if date_str == "Unknown":
        digital_date = soup.find(string=re.compile("Digital Order:"))
        if digital_date:
            date_str = clean_date(digital_date)

    # --- 2. EXTRACT TOTAL ---
    total = "0.00"
    total_tag = soup.find(string=re.compile("Grand Total"))
    if total_tag:
        parent = total_tag.find_parent("div") or total_tag.parent.parent
        total = clean_price(parent.get_text())

    # --- 3. EXTRACT ITEMS ---
    # Physical
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
                "link": href
            })
        except: continue

    # Digital
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
                    "link": link.get("href")
                })

    return {
        "id": order_id,
        "date": date_str,
        "total": total,
        "items": items
    }

async def worker(name, queue, page, results, existing_ids):
    while True:
        order_meta = await queue.get()
        if order_meta is None: break

        if order_meta['id'] in existing_ids:
            queue.task_done()
            continue

        print(f"[{name}] Fetching {order_meta['id']}...")
        await asyncio.sleep(random.uniform(1.0, 3.0))

        html = await fetch_order_html(page, order_meta['url'])
        
        if html:
            data = parse_order_page(html, order_meta['id'])
            
            # --- CRITICAL FIX: META DATE FALLBACK ---
            # If the Detail Page parser returned "Unknown", we use the date 
            # we scraped from the List Page (order_meta['date'])
            if data['date'] == "Unknown" and order_meta['date'] != "Unknown":
                data['date'] = clean_date(order_meta['date'])
            
            results.append(data)
            
            item_summary = f"{data['items'][0]['description'][:20]}..." if data['items'] else "No items"
            print(f"   + {data['id']} | {data['date']} | ${data['total']} | {item_summary}")
        else:
            print(f"   [Error] Failed to fetch HTML for {order_meta['id']}")

        queue.task_done()

async def main():
    print("--- AMAZON INGESTION v10 (Date Fix) ---")
    
    existing_data = []
    if os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, "r") as f:
                existing_data = json.load(f)
            print(f"Loaded {len(existing_data)} existing orders.")
        except:
            print("Starting fresh.")
            
    existing_ids = set(item['id'] for item in existing_data)

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 720},
        )
        page = await browser.new_page()
        
        # 1. Get Years
        print("Checking available years...")
        await page.goto("https://www.amazon.com/your-orders/orders?timeFilter=year-2025")
        
        try:
            await page.wait_for_selector("#time-filter", timeout=5000)
        except:
            print("!!! PLEASE LOG IN !!!")
            await page.wait_for_selector("#time-filter", timeout=300000)
            
        years = await page.evaluate("""
            () => {
                const select = document.querySelector('#time-filter');
                return Array.from(select.options)
                    .map(o => o.value)
                    .filter(v => v.startsWith('year-'));
            }
        """)
        
        print(f"Found Years: {years}")
        
        # 2. Harvest URLs (With Robust List-Page Date Scraping)
        all_order_metas = []
        
        for year_val in years:
            print(f"\nScanning {year_val}...")
            await page.goto(f"https://www.amazon.com/your-orders/orders?timeFilter={year_val}")
            
            while True:
                # --- UPDATED JAVASCRIPT FOR LIST PAGE ---
                metas = await page.evaluate("""
                    () => {
                        return Array.from(document.querySelectorAll('.js-order-card')).map(row => {
                            const link = row.querySelector("a[href*='order-details']");
                            const id = row.innerText.match(/\\d{3}-\\d{7}-\\d{7}/)?.[0] || 'Unknown';
                            
                            // DATE EXTRACTION STRATEGY:
                            // Find the "Order placed" label, then look for the text in the next div
                            let date = 'Unknown';
                            const labels = Array.from(row.querySelectorAll('span'));
                            const dateLabel = labels.find(s => s.innerText.trim().toUpperCase() === 'ORDER PLACED');
                            
                            if (dateLabel) {
                                // Based on user HTML: Grandparent row -> Next Sibling row -> Span
                                const parentRow = dateLabel.closest('.a-row');
                                if (parentRow && parentRow.nextElementSibling) {
                                    date = parentRow.nextElementSibling.innerText.trim();
                                }
                            }

                            return { url: link ? link.href : null, id: id, date: date };
                        });
                    }
                """)
                
                new_count = 0
                for m in metas:
                    if m['id'] != 'Unknown' and m['id'] not in existing_ids:
                        all_order_metas.append(m)
                        new_count += 1
                
                print(f"   Found {len(metas)} orders (New: {new_count})")

                next_btn = page.locator(".a-last a")
                if await next_btn.count() > 0:
                    await next_btn.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(1.5)
                else:
                    break
                    
        unique_metas = {m['id']: m for m in all_order_metas}.values()
        print(f"\nTotal New Orders to Process: {len(unique_metas)}")
        
        # 3. Process
        if unique_metas:
            queue = asyncio.Queue()
            new_results = []
            
            for m in unique_metas: queue.put_nowait(m)

            tasks = [asyncio.create_task(worker(f"W-{i}", queue, page, new_results, existing_ids)) 
                     for i in range(MAX_CONCURRENCY)]
            
            await queue.join()
            for _ in range(MAX_CONCURRENCY): queue.put_nowait(None)
            await asyncio.gather(*tasks)
            
            existing_data.extend(new_results)
            
            with open(OUTPUT_JSON, "w") as f:
                json.dump(existing_data, f, indent=2)
            print(f"Updated JSON saved to {OUTPUT_JSON}")

        # 4. Export CSV
        print("Exporting to CSV...")
        csv_rows = []
        for order in existing_data:
            if not order['items']:
                 csv_rows.append({
                    "Date": order['date'],
                    "Order ID": order['id'],
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
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())