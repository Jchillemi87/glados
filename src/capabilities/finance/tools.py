from langchain_core.tools import tool
from sqlalchemy import text
from src.core.database import get_db_session

@tool
def query_amazon_orders(sql_query: str) -> str:
    """
    Executes a SQLite query against the 'amazon_orders' table.
    
    SCHEMA:
    - order_id (TEXT)
    - date (DATE, format YYYY-MM-DD)
    - item_description (TEXT)
    - item_price (FLOAT)
    - quantity (INTEGER)
    - category (TEXT)
    - link (TEXT)

    RULES:
    1. SELECT statements ONLY. No INSERT/UPDATE/DELETE/DROP.
    2. Do not use markdown formatting in the query.
    3. Use 'LIKE' for text searches (e.g. item_description LIKE '%sushi%').
    4. Limit results to 20 unless specifically asked for more.
    """
    # 1. Safety Check (Basic SQL Injection/Destruction Guard)
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "GRANT"]
    if any(verb in sql_query.upper() for verb in forbidden):
        return "SECURITY ALERT: Write operations are forbidden. Read-only access allowed."

    # 2. Execution
    session = get_db_session()
    try:
        # Wrap query for SQLAlchemy
        result = session.execute(text(sql_query))
        rows = result.fetchall()
        
        if not rows:
            return "Query returned no results."
            
        # 3. Formatting
        # Get column names from keys
        columns = list(result.keys())
        output = [f"Found {len(rows)} records:", " | ".join(columns)]
        
        for row in rows:
            # Convert row to string representation
            row_str = " | ".join(str(item) for item in row)
            output.append(row_str)
            
        return "\n".join(output)

    except Exception as e:
        return f"SQL ERROR: {e}"
    finally:
        session.close()