import os
import chromadb
from chromadb.config import Settings

class ChromaStore:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChromaStore, cls).__new__(cls)
            # Initialize persistent client
            chroma_dir = os.path.join(os.getcwd(), "data", "chroma")
            os.makedirs(chroma_dir, exist_ok=True)
            cls._instance._client = chromadb.PersistentClient(path=chroma_dir)
        return cls._instance

    def _get_collection_name(self, project_id: str) -> str:
        return f"refyne_project_{project_id.replace('-', '_')}"

    def get_or_create_collection(self, project_id: str):
        collection_name = self._get_collection_name(project_id)
        return self._client.get_or_create_collection(name=collection_name)

    def upsert_chunks(self, project_id: str, chunks: list[dict], embeddings: list[list[float]]):
        """
        Upserts chunks to the project collection.
        Chunks must contain 'text' and 'metadata'.
        """
        collection = self.get_or_create_collection(project_id)
        
        ids = []
        texts = []
        metadatas = []
        
        for chunk in chunks:
            doc_id = chunk["metadata"]["document_id"]
            chunk_idx = chunk["metadata"]["chunk_index"]
            # Deterministic ID
            chunk_id = f"{doc_id}_{chunk_idx}"
            
            ids.append(chunk_id)
            texts.append(chunk["text"])
            
            # Ensure metadata values are str, int, float, or bool for ChromaDB
            clean_meta = {}
            for k, v in chunk["metadata"].items():
                if v is not None:
                    clean_meta[k] = v
            metadatas.append(clean_meta)
            
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

    def delete_document_chunks(self, project_id: str, document_id: str):
        """
        Deletes all chunks for a specific document in the project collection.
        """
        try:
            collection = self.get_or_create_collection(project_id)
            # ChromaDB supports deleting by where clause
            collection.delete(where={"document_id": document_id})
        except Exception:
            pass

def get_chroma_store() -> ChromaStore:
    return ChromaStore()
