import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/database/refyne.db"
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    CORS_ORIGINS: str = "http://localhost:5173"
    
    # Document settings
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".doc", ".docx", ".xlsx", ".csv", ".txt"]
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # Phase 3: Hybrid RAG Retrieval settings
    # Fusion weights must sum to 1.0 (validated at startup)
    HYBRID_SEMANTIC_WEIGHT: float = 0.6
    HYBRID_BM25_WEIGHT: float = 0.4
    # Min normalized hybrid score to include a result (0.0–1.0)
    HYBRID_MIN_SCORE: float = 0.10
    # Default number of final results to return
    RETRIEVAL_TOP_K: int = 8
    # Maximum allowed top_k from API requests
    RETRIEVAL_MAX_TOP_K: int = 20
    # Candidate pool multiplier: fetch top_k * multiplier from each retriever before fusion
    RETRIEVAL_CANDIDATE_MULTIPLIER: int = 3
    # Maximum context characters sent to LLM (future use)
    MAX_CONTEXT_CHARS: int = 30000
    # Enable retrieval debug info in API responses (never expose in production)
    RETRIEVAL_DEBUG: bool = False

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
