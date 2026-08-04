"""Process-wide configuration read from the environment, once, at import.

Module constants rather than a settings object: these are fixed for the life of
the process (they come from `.env`), so a getter would imply a mutability that
does not exist. Anything a *user* can change belongs in `core/settings_store.py`
instead — the split is "who owns this value", not "what type is it".

The Kite values are intentionally left as `None` when unset rather than
defaulted, so a missing credential fails at the Kite call with a clear error
instead of silently authenticating as nobody.
"""
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("KITE_API_KEY")
API_SECRET = os.getenv("KITE_API_SECRET")
REDIRECT_URL = os.getenv("REDIRECT_URL")
FRONTEND_URL = os.getenv("FRONTEND_URL")

# Local-first LLM for the in-app Agent tab (OpenAI-compatible endpoint).
# Defaults target Ollama; override to point at any OpenAI-compatible provider.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")