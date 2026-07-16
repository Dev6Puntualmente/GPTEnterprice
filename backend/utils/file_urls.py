from pathlib import Path


def public_file_url(filename: str) -> str:
    """URL relativa para el front Next.js (/api/files → proxy a FastAPI)."""
    safe = Path(filename).name
    return f"/api/files/{safe}"
