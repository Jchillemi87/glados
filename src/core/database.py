# src/core/database.py
from sqlalchemy import create_engine, Column, String, Float, Integer, Text, Date
from sqlalchemy.orm import sessionmaker, declarative_base
from src.core.config import settings

# 1. Database Setup
# We use a local SQLite file. 'check_same_thread=False' is needed for multi-threaded agents.
DB_URL = "sqlite:///finance_data.db" 

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. The Model (Schema)
class AmazonOrder(Base):
    """
    Represents a single line item from an Amazon Order.
    Since one Order ID can have multiple items, we store them as individual rows.
    """
    __tablename__ = "amazon_orders"

    # Primary Key (Internal ID)
    id = Column(Integer, primary_key=True, index=True)
    
    # Order Metadata
    order_id = Column(String, index=True)      # "113-1234567..."
    date = Column(Date, index=True)            # 2025-01-01
    
    # Item Details
    item_description = Column(Text)            # "Ninja Blender..."
    item_price = Column(Float)                 # 99.99
    quantity = Column(Integer)                 # 1
    category = Column(String)                  # "Physical" or "Digital"
    link = Column(String)                      # URL to product

# 3. Initialization
def init_db():
    """Creates the tables if they don't exist."""
    Base.metadata.create_all(bind=engine)

def get_db_session():
    """Factory to get a new DB session."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise