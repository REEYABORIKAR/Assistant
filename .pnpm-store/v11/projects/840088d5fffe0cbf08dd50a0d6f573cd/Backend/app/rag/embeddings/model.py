from sentence_transformers import SentenceTransformer

class EmbeddingModelSingleton:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingModelSingleton, cls).__new__(cls)
            # Load the model only once
            cls._instance._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return cls._instance

    def embed_text(self, text: str) -> list[float]:
        return self._model.encode(text).tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts).tolist()

def get_embedding_model() -> EmbeddingModelSingleton:
    return EmbeddingModelSingleton()
