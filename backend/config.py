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