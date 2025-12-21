import os
import json
import sys

# Constants
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1

def get_project_root():
    # src/lib/gemini_client.py -> src/lib -> src -> root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_config():
    root = get_project_root()
    config_path = os.path.join(root, 'ai_config.json')
    
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Config load error: {e}")
        return None

def get_api_key():
    config = load_config()
    if config and 'gemini' in config:
        return config['gemini'].get('apiKey')
    return os.environ.get("GEMINI_API_KEY")

def get_gemini_client():
    """
    Returns a configured google.genai.Client instance.
    Requires 'google-genai' package (the new SDK).
    """
    try:
        from google import genai
    except ImportError:
        print("Error: 'google-genai' package is required. Please install it.")
        sys.exit(1)

    api_key = get_api_key()
    if not api_key:
        raise ValueError("Gemini API Key not found in ai_config.json or environment variables.")

    return genai.Client(api_key=api_key)
