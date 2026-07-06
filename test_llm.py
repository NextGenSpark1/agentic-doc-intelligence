# test_llm.py
import os
from dotenv import load_dotenv

# Load .env from the project root – override any existing env vars
load_dotenv(override=True)

# Debug: show which key the process sees
gemini_key = os.getenv("GEMINI_API_KEY")
print("🔑 GEMINI_API_KEY loaded →", repr(gemini_key))
print("Length →", len(gemini_key) if gemini_key else "MISSING")

# -----------------------------------------------------------------
# Normal test logic (keep your existing debug output)
import litellm
litellm._turn_on_debug()

from backend.llm import complete, embed

def test_ai():
    print("\nTesting LLM (Groq)...")
    try:
        response = complete(
            messages=[{"role": "user", "content": "Say 'Groq is working' if you receive this."}],
            tier="fast",
        )
        print(f"Success! Response: {response}")
    except Exception as e:
        print(f"LLM Error: {e}")

    print("\nTesting Embeddings (Gemini)...")
    try:
        # Simple test string – replace with any text you want to embed
        emb = embed(["Hello world"])
        print("Success! Embeddings returned:", emb[:1])  # show the first vector
    except Exception as e:
        print(f"Embeddings Error: {e}")

if __name__ == "__main__":
    test_ai()


import os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("GEMINI_API_KEY")
print(repr(key))
print(len(key) if key else "MISSING")