# %% src/scripts/delete_doc_from_qdrant.py
import sys
import os

# 1. Setup path to import from src (same as your ingest script)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from qdrant_client.http import models
from src.core.vector import get_qdrant_client

# 2. Config
COLLECTION_NAME = "personal_knowledge"
TARGET_SOURCE_ID = "paperless_id_10"  # The ID you confirmed via Scroll

def run_delete():
    print(f"--- DELETING: {TARGET_SOURCE_ID} ---")
    client = get_qdrant_client()

    # 3. verify collection exists
    if not client.collection_exists(COLLECTION_NAME):
        print(f"Collection '{COLLECTION_NAME}' not found!")
        return

    # 4. Perform Delete
    # We use FilterSelector to delete by metadata, not by Point ID (UUID)
    result = client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.source",
                        match=models.MatchValue(value=TARGET_SOURCE_ID)
                    )
                ]
            )
        )
    )

    print(f"Operation status: {result.status}")
    print("Document deleted. You can now re-run ingest_paperless.py.")

if __name__ == "__main__":
    run_delete()