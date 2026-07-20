import os

PROVIDERS = {
    "gemini": {
        "key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.5-flash",
        "label": "Google Gemini",
    },
    "openai": {
        "key_env": "OPENAI_API_KEY",
        "base_url": None,
        "default_model": "gpt-4o-mini",
        "label": "OpenAI GPT",
    },
}


def _resolve(provider_env, model_env):
    primary = os.getenv(provider_env, "gemini").strip().lower()
    if primary not in PROVIDERS:
        primary = "gemini"
    order = [primary] + [name for name in PROVIDERS if name != primary]
    for provider in order:
        cfg = PROVIDERS[provider]
        key = (os.getenv(cfg["key_env"]) or "").strip()
        if not key:
            continue
        model = cfg["default_model"]
        if provider == primary:
            model = (os.getenv(model_env) or "").strip() or model
        return {
            "provider": provider,
            "label": cfg["label"],
            "api_key": key,
            "base_url": cfg["base_url"],
            "model": model,
        }
    return None
