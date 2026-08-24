import os
import pickle

from rank_bm25 import BM25Okapi


class BM25Index:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_dir = os.path.join(os.getcwd(), "data", "bm25", project_id)
        os.makedirs(self.storage_dir, exist_ok=True)
        self.index_path = os.path.join(self.storage_dir, "index.pkl")
        self.metadata_path = os.path.join(self.storage_dir, "metadata.pkl")

        self.bm25: BM25Okapi | None = None
        self.corpus = []
        self.metadatas = []

        self._load()

    def _load(self):
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                with open(self.index_path, "rb") as f:
                    self.bm25 = pickle.load(f)
                with open(self.metadata_path, "rb") as f:
                    data = pickle.load(f)
                    self.corpus = data.get("corpus", [])
                    self.metadatas = data.get("metadatas", [])
            except Exception:
                # If corrupted, reset
                self.bm25 = None
                self.corpus = []
                self.metadatas = []

    def _save(self):
        with open(self.index_path, "wb") as f:
            pickle.dump(self.bm25, f)
        with open(self.metadata_path, "wb") as f:
            pickle.dump({"corpus": self.corpus, "metadatas": self.metadatas}, f)

    def rebuild_from_chunks(self, chunks: list[dict]):
        """
        Rebuilds the entire index from a list of chunk dicts.
        Each chunk must have 'text' and 'metadata'.
        """
        self.corpus = []
        self.metadatas = []

        for chunk in chunks:
            self.corpus.append(chunk["text"])
            self.metadatas.append(chunk["metadata"])

        if self.corpus:
            tokenized_corpus = [doc.split(" ") for doc in self.corpus]
            self.bm25 = BM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None

        self._save()

    def add_chunks(self, chunks: list[dict]):
        """
        Adds new chunks to the existing index and rebuilds.
        """
        for chunk in chunks:
            self.corpus.append(chunk["text"])
            self.metadatas.append(chunk["metadata"])

        if self.corpus:
            tokenized_corpus = [doc.split(" ") for doc in self.corpus]
            self.bm25 = BM25Okapi(tokenized_corpus)

        self._save()

    def remove_document(self, document_id: str):
        """
        Removes all chunks associated with a document_id and rebuilds.
        """
        new_corpus = []
        new_metadatas = []

        for text, meta in zip(self.corpus, self.metadatas):
            if meta.get("document_id") != document_id:
                new_corpus.append(text)
                new_metadatas.append(meta)

        self.corpus = new_corpus
        self.metadatas = new_metadatas

        if self.corpus:
            tokenized_corpus = [doc.split(" ") for doc in self.corpus]
            self.bm25 = BM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None

        self._save()
