"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend directory
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class Settings:
    """Central configuration — all values from .env."""

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # ── Gemini ───────────────────────────────────────────────────
    GEMINI_API_KEY_RAW: str = os.getenv("GEMINI_API_KEY", "")
    
    @property
    def GEMINI_API_KEYS(self) -> list[str]:
        """Return list of API keys for rotation."""
        return [k.strip() for k in self.GEMINI_API_KEY_RAW.split(",") if k.strip()]


    # ── JWT ──────────────────────────────────────────────────────
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")
    )

    # ── Storage paths ────────────────────────────────────────────
    PDF_STORAGE_PATH: str = os.getenv(
        "PDF_STORAGE_PATH",
        str(Path(__file__).resolve().parent.parent / "data" / "pdfs"),
    )
    QDRANT_PATH: str = os.getenv(
        "QDRANT_PATH",
        str(Path(__file__).resolve().parent.parent / "data" / "qdrant"),
    )
    # If set, connect to Qdrant cluster via HTTP (Docker or Qdrant Cloud)
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    # Required for Qdrant Cloud
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")

    # ── App ──────────────────────────────────────────────────────
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # ── Chunking ──────────────────────────────────────────────────
    CHILD_CHUNK_SIZE: int = int(os.getenv("CHILD_CHUNK_SIZE", "1500"))
    CHILD_CHUNK_OVERLAP: int = int(os.getenv("CHILD_CHUNK_OVERLAP", "200"))

    # ── Model names (centralized, overridable via env) ───────────
    # We default to 3.1-flash-lite because it offers 500 Requests/Day on free tier
    GEMINI_FLASH_MODEL: str = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    GEMINI_PRO_MODEL: str = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")
    GEMINI_FLASH_LITE_MODEL: str = os.getenv("GEMINI_FLASH_LITE_MODEL", "gemini-2.5-flash-lite")
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    SPARSE_MODEL: str = "Qdrant/bm25"
    DENSE_DIM: int = 768
    COLLECTION_NAME: str = "upsc_chunks"

    # ── Rate Limits ──────────────────────────────────────────────
    FLASH_LITE_MIN_INTERVAL: float = float(os.getenv("FLASH_LITE_MIN_INTERVAL", "4.0"))
    FLASH_MIN_INTERVAL: float = float(os.getenv("FLASH_MIN_INTERVAL", "6.0"))
    PRO_MIN_INTERVAL: float = float(os.getenv("PRO_MIN_INTERVAL", "12.0"))

    # ── CORS ─────────────────────────────────────────────────────
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000")
    CORS_ORIGIN_REGEX: str = os.getenv("CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app")


settings = Settings()

# ── Production safety check ──────────────────────────────────────
if settings.ENVIRONMENT != "development" and settings.JWT_SECRET == "dev-secret-change-me":
    raise RuntimeError(
        "FATAL: JWT_SECRET is still the default dev value in a non-development environment. "
        "Set a strong JWT_SECRET in your .env or environment variables."
    )
