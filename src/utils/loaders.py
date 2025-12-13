# Extracted entirely from paperless_example.py
import requests
from typing import Iterator
from langchain_core.documents import Document
from langchain_core.document_loaders import BaseLoader

class CustomPaperlessLoader(BaseLoader):
    """
    A custom loader that connects to a local Paperless-ngx instance.
    It fetches OCR'd text and preserves metadata.
    """
    def __init__(self, url: str, api_token: str):
        self.url = url.rstrip('/')
        self.headers = {"Authorization": f"Token {api_token}"}

    def lazy_load(self) -> Iterator[Document]:
        next_page = f"{self.url}/api/documents/"
        
        while next_page:
            print(f"   Fetching page: {next_page}...")
            try:
                response = requests.get(next_page, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                for doc_data in data.get("results", []):
                    # Only yield if there is actual text content
                    content = doc_data.get("content", "").strip()
                    if content:
                        yield Document(
                            page_content=content,
                            metadata={
                                "source": f"paperless_id_{doc_data.get('id')}",
                                "title": doc_data.get("title", "Untitled"),
                                "created": doc_data.get("created", ""),
                                "correspondent": doc_data.get("correspondent", "Unknown"),
                                "tags": doc_data.get("tags", [])
                            }
                        )
                
                next_page = data.get("next") # Pagination handling
                
            except Exception as e:
                print(f"Error fetching from Paperless: {e}")
                break