"""aihelper: free-tier AI coding helper with automatic model discovery and fallback.

Works in Google Colab, Kaggle, VS Code / local Python (keys from Secrets or env vars).
Usage:
    from aihelper import ask, code, fix, set_project
"""
import os
import re

__all__ = ["ask", "code", "fix", "set_project", "rebuild"]

# ---------------------------------------------------------------- keys
def get(name):
    """Read a key from Colab Secrets, Kaggle Secrets, or environment variables."""
    try:
        from google.colab import userdata
        return userdata.get(name)
    except Exception:
        pass
    try:
        from kaggle_secrets import UserSecretsClient
        return UserSecretsClient().get_secret(name)
    except Exception:
        pass
    return os.environ.get(name)


# ---------------------------------------------------------------- providers
# name, litellm prefix, base_url (used only to LIST models), key name,
# preferred words (best first), must-contain filter. Order = fallback order.
PROVIDERS = [
    ("gemini", "gemini", "https://generativelanguage.googleapis.com/v1beta/openai/",
     "GEMINI_API_KEY", ["flash", "pro"], None),
    ("groq", "groq", "https://api.groq.com/openai/v1",
     "GROQ_API_KEY", ["llama-3.3", "qwen", "gpt-oss", "llama"], None),
    ("openrouter", "openrouter", "https://openrouter.ai/api/v1",
     "OPENROUTER_API_KEY", ["coder", "deepseek", "qwen", "llama", "gemini"], ":free"),
]

NOT_CHAT = ["embed", "whisper", "tts", "guard", "vision", "image", "imagen",
            "aqa", "audio", "live", "moderation", "robotics"]

_router = None
_active = []

PROJECT = "Environment: Python 3 (Google Colab / Kaggle / local). Prefer short, commented code."


def set_project(text):
    """Describe your project once so generated code matches your data and goals."""
    global PROJECT
    PROJECT = text


# ---------------------------------------------------------------- discovery
def _pick_model(base_url, key, prefer, must):
    from openai import OpenAI
    ids = [m.id.replace("models/", "")
           for m in OpenAI(base_url=base_url, api_key=key).models.list().data]
    ids = [i for i in ids if not any(x in i.lower() for x in NOT_CHAT)]
    if must:
        ids = [i for i in ids if must in i]
    if not ids:
        return None

    def score(i):
        low = i.lower()
        rank = next((n for n, w in enumerate(prefer) if w in low), len(prefer))
        unstable = any(x in low for x in ["preview", "exp", "latest"])
        return (rank, unstable, len(i))

    return sorted(ids, key=score)[0]


def rebuild(verbose=True):
    """(Re)discover available models and rebuild the LiteLLM router."""
    global _router, _active
    from litellm import Router
    model_list, _active = [], []
    for name, prefix, url, key_name, prefer, must in PROVIDERS:
        key = get(key_name)
        if not key:
            if verbose:
                print(f"  {name} skipped: no {key_name} found")
            continue
        try:
            model = _pick_model(url, key, prefer, must)
            if model:
                model_list.append({"model_name": name,
                                   "litellm_params": {"model": f"{prefix}/{model}",
                                                      "api_key": key}})
                _active.append(name)
                if verbose:
                    print(f"  {name}: {prefix}/{model}")
        except Exception as e:
            if verbose:
                print(f"  {name} skipped: {str(e)[:120]}")
    if not model_list:
        raise RuntimeError("No provider available. Check keys and (on Kaggle) that Internet is ON.")
    fallbacks = [{_active[i]: _active[i + 1:]} for i in range(len(_active) - 1)]
    _router = Router(model_list=model_list, fallbacks=fallbacks, num_retries=1, timeout=60)


# ---------------------------------------------------------------- ask / code / fix
def ask(prompt, system="You are a helpful Python coding tutor. Explain briefly."):
    """Send a prompt; falls back across providers; re-discovers models once if all fail."""
    if _router is None:
        print("Discovering models...")
        rebuild()
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    for attempt in range(2):
        try:
            r = _router.completion(model=_active[0], messages=msgs)
            print(f"[answered by {r.model}]\n")
            return r.choices[0].message.content
        except Exception as e:
            print(f"All routes failed: {str(e)[:200]}")
            if attempt == 0:
                print("Re-discovering models and retrying...")
                try:
                    rebuild()
                except Exception as e2:
                    return f"Could not rebuild: {e2}"
    return "Still failing. Likely rate limits on all providers; wait a bit or add a local Ollama model."


def code(task, explain=False):
    """Ask for code. In a notebook it opens in a NEW cell below so you can read before running."""
    system = ("You are a Python coding tutor. Reply with ONE Python code block that runs as-is, "
              "with comments on each step. "
              + ("Then add a short explanation of the key lines. " if explain
                 else "No text outside the code block. ")
              + "\n" + PROJECT)
    reply = ask(task, system=system)
    match = re.search(r"```(?:python)?\n(.*?)```", reply, re.S)
    snippet = match.group(1) if match else reply
    try:
        get_ipython().set_next_input(snippet)   # notebook / IPython
    except NameError:
        print(snippet)                           # plain Python
    if explain:
        print(reply)


def fix(error, broken_code=""):
    """Paste the full traceback (and the code) to get a corrected version."""
    code(f"This code failed.\n\nCode:\n{broken_code}\n\nError:\n{error}\n\n"
         "Explain in one line what went wrong, then give the corrected code.")


# ---------------------------------------------------------------- %%ai cell magic
try:
    from IPython import get_ipython as _gi
    _ip = _gi()
    if _ip is not None:
        from IPython.display import Markdown, display

        def _ai(line, cell):
            display(Markdown(ask(cell)))

        _ip.register_magic_function(_ai, magic_kind="cell", magic_name="ai")
except Exception:
    pass
