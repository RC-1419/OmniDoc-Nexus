import sys
import time

from omnidoc.providers.llm.base import LLMError
from omnidoc.providers.llm.factory import configured_providers, get_llm, provider_label
from omnidoc.providers.llm.fallback import FallbackLLM
from omnidoc.providers.llm.openai_compat import OpenAICompatProvider

names = configured_providers()
if not names:
    raise SystemExit(
        "No API keys found in .env (GROQ_API_KEY, MISTRAL_API_KEY, GEMINI_API_KEY ...)")
print("configured providers:", ", ".join(provider_label(n) for n in names))

if "--models" in sys.argv:  # lists the model ids each provider offers right now
    for n in names:
        try:
            ids = get_llm(n).list_models()
            if n == "openrouter":
                ids = [i for i in ids if i.endswith(":free")]
            print(f"\n{n}: {len(ids)} models")
            print("\n".join("  " + i for i in ids[:100]))
        except LLMError as e:
            print(f"\n{e}")
    raise SystemExit

TOOLS = [{"type": "function", "function": {
    "name": "get_document_field",
    "description": "Look up a stored value from the user's documents, such as a PAN or Aadhaar number.",
    "parameters": {"type": "object",
                   "properties": {"doc_type": {"type": "string", "enum": ["aadhaar", "pan", "passport"]},
                                  "field": {"type": "string"}},
                   "required": ["doc_type"]}}}]


def step(label, fn):
    try:
        t = time.time()
        print(f"{label:<14}{fn()}  ({time.time() - t:.1f}s)")
    except LLMError as e:
        print(f"{label:<14}FAILED: {e}")


for n in names:
    llm = get_llm(n)
    print(f"\n== {provider_label(n)} ({llm.model}) ==")
    step("plain chat:", lambda: repr((llm.chat(
        [{"role": "user", "content": "Reply with the single word: pong"}]).text or "").strip()[:40]))
    step("json mode:", lambda: (llm.chat(
        [{"role": "system", "content": 'Classify the request. Return only JSON like {"action": "answer" | "show_document" | "email_document"}.'},
         {"role": "user", "content": "Email my PAN card to my sister"}], json_mode=True).text or "").strip()[:80])
    step("tool calling:", lambda: str([(c.name, c.arguments) for c in llm.chat(
        [{"role": "user", "content": "What is my PAN number?"}], tools=TOOLS).tool_calls] or "no tool call"))

print("\n== fallback ==")
first = names[0]
broken = OpenAICompatProvider(first, api_key="invalid-key")
try:
    r = FallbackLLM([broken, get_llm(first)]).chat(
        [{"role": "user", "content": "Reply with the single word: pong"}])
    print(
        f"invalid key first, then the real one: answered by {r.provider}: {(r.text or '').strip()[:40]!r}")
except LLMError as e:
    print("fallback test failed:", e)
