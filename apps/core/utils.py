def safe_next(value, fallback="/"):
    if not value:
        return fallback
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
