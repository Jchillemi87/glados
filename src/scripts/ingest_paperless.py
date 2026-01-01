# %% src/scripts/ingest_paperless.py

import sys
import os
import time
import math
from typing import List
from tqdm import tqdm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from langchain_experimental.text_splitter import SemanticChunker
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from qdrant_client.http import models

from src.core.config import settings
from src.core.llm import get_embeddings
from src.core.vector import get_qdrant_client
from src.utils.loaders import CustomPaperlessLoader

COLLECTION_NAME = "personal_knowledge"
EST_CHARS_PER_PAGE = 3000  # Rough heuristic to estimate "work" involved

def get_existing_doc_stats(client, collection_name: str, source_id: str) -> str | None:
    """Queries Qdrant to find the 'modified' timestamp of an existing document."""
    try:
        results = client.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.source",
                        match=models.MatchValue(value=source_id)
                    )
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False
        )
        points = results[0]
        if points:
            return points[0].payload.get("metadata", {}).get("modified")
        return None
    except Exception:
        return None

def estimate_pages(text: str) -> int:
    """Returns an estimated page count based on character length."""
    if not text:
        return 0
    return math.ceil(len(text) / EST_CHARS_PER_PAGE)

def process_one_by_one(documents: List[Document], vector_store: QdrantVectorStore, text_splitter: SemanticChunker):
    """
    Processes documents individually to provide granular feedback.
    """
    # Calculate total work (in estimated pages)
    total_est_pages = sum(estimate_pages(d.page_content) for d in documents)
    
    print(f"\n--- PROCESSING QUEUE ---")
    print(f"Total Documents: {len(documents)}")
    print(f"Total Est. Pages: {total_est_pages} (approx. {EST_CHARS_PER_PAGE} chars/page)")
    print("-" * 30)

    # Iterate with a progress bar weighted by PAGE COUNT
    with tqdm(total=total_est_pages, unit="pg", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} pages [{elapsed}<{remaining}]") as pbar:
        
        for doc in documents:
            # metadata.get("title") is preferred, fallback to source/filename
            filename = doc.metadata.get("title", doc.metadata.get("source", "Unknown Document"))
            # Truncate filename for cleaner display
            display_name = (filename[:30] + '..') if len(filename) > 30 else filename
            
            # Calculate this specific doc's size
            doc_pages = estimate_pages(doc.page_content)
            
            # Update description so user sees WHICH file is blocking
            pbar.set_description(f"Processing: {display_name}")

            # SPLIT (The bottleneck)
            # This is where the script hangs while calculating embeddings
            # We pass [doc] as a list containing a single document
            chunks = text_splitter.split_documents([doc])

            # UPLOAD
            if chunks:
                vector_store.add_documents(chunks)
            
            # Update progress bar by the size of the document just finished
            pbar.update(doc_pages)

def run_ingestion():
    print(f"--- STARTING INCREMENTAL INGESTION: {COLLECTION_NAME} ---")
    
    # Connect
    client = get_qdrant_client()
    embeddings = get_embeddings()

    # SAFETY CHECK
    test_embedding = embeddings.embed_query("test")
    current_dim = len(test_embedding)

    if client.collection_exists(COLLECTION_NAME):
        collection_info = client.get_collection(COLLECTION_NAME)
        stored_dim = collection_info.config.params.vectors.size
        
        if current_dim != stored_dim:
            print(f"\nCRITICAL ERROR: Embedding Dimension Mismatch!")
            print(f"   Current: {current_dim} vs Stored: {stored_dim}")
            sys.exit(1)
    # ---------------------

    # Create Collection
    if not client.collection_exists(COLLECTION_NAME):
        print(f"Collection '{COLLECTION_NAME}' not found. Creating it...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=current_dim, distance=models.Distance.COSINE)
        )

    # Fetch
    print(f"Fetching docs from {settings.PAPERLESS_URL}...")
    loader = CustomPaperlessLoader(
        url=settings.PAPERLESS_URL,
        api_token=settings.PAPERLESS_API_TOKEN
    )
    raw_docs = list(loader.lazy_load())
    
    if not raw_docs:
        print("No documents found.")
        return

    print(f"Fetched {len(raw_docs)} documents.")

    docs_to_add: List[Document] = []
    ids_to_delete: List[str] = []
    stats = {"new": 0, "updated": 0, "skipped": 0}

    # Filter Loop
    print("Checking status against Qdrant...")
    for doc in tqdm(raw_docs, desc="Filtering", unit="doc"):
        source_id = doc.metadata.get("source")
        new_modified = doc.metadata.get("modified")

        if not source_id:
            continue

        stored_modified = get_existing_doc_stats(client, COLLECTION_NAME, source_id)

        if stored_modified is None:
            stats["new"] += 1
            docs_to_add.append(doc)
        elif new_modified != stored_modified:
            stats["updated"] += 1
            ids_to_delete.append(source_id)
            docs_to_add.append(doc)
        else:
            stats["skipped"] += 1

    print(f"\n--- SYNC PLAN ---")
    print(f"Skipping: {stats['skipped']}")
    print(f"Updating: {stats['updated']}")
    print(f"Adding:   {stats['new']}")
    
    if not docs_to_add:
        print("System is up to date. Exiting.")
        return

    # Deletions
    if ids_to_delete:
        print(f"Removing {len(ids_to_delete)} old versions...")
        for source_id in tqdm(ids_to_delete, desc="Deleting Old"):
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="metadata.source",
                                match=models.MatchValue(value=source_id)
                            )
                        ]
                    )
                )
            )

    # Initialize VectorStore
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embeddings,
    )
    
    # Initialize Splitter
    print("\nInitializing Semantic Splitter (This uses your Embedding Model)...")
    text_splitter = SemanticChunker(
        embeddings, 
        breakpoint_threshold_type="percentile"
    )

    # Run the new One-by-One Processor
    process_one_by_one(docs_to_add, vector_store, text_splitter)

    print("\n--- INGESTION COMPLETE ---")

if __name__ == "__main__":
    start_time = time.time()
    run_ingestion()
    print(f"Total Runtime: {time.time() - start_time:.2f}s")