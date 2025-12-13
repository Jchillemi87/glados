# srccorepersistence.py
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from src.core.config import settings

def get_checkpointer():
    
    # Creates a SQLite-backed checkpointer for conversation history.
    
    # check_same_thread=False is needed because FastAPILangGraph runs async
    conn = sqlite3.connect(settings.STATE_DB_PATH, check_same_thread=False)
    
    # The 'memory' object manages readingwriting state to the DB
    return SqliteSaver(conn)