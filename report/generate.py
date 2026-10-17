"""
report/generate.py - TrustTrace AI report (Member 4)

Takes the risk JSON, asks a small LOCAL LLM (Ollama or llama.cpp) to write a
short plain-language report, then CHECKS the answer against our safety rules.
If the model breaks a rule twice, we use a safe template so the demo never fails.

Uses only the Python standard library -> nothing to install on s390x.

Run the demo from the repo root:  python3 -m report.generate

Settings (environment variables, all optional):
  LLM_BACKEND   "ollama" (default) or "llamacpp"
  OLLAMA_URL    default http://localhost:11434
  LLAMACPP_URL  default http://localhost:8080   (llama-server)
  LLM_MODEL     default granite3.3:2b           (check with: ollama list)
"""

import json
import os
import re
import urllib.request

from report.prompt import BANNED_PATTERN, MAX_WORDS, SYSTEM_PROMPT

LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLAMACPP_URL = os.getenv("LLAMACPP_URL", "http://localhost:8080")
LLM_MODEL = os.getenv("LLM_MODEL", "granite3.3:2b")


# ---------------------------------------------------------------------------
# 1. The system prompt (the rules the model must follow)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 2. Small helpers
# ---------------------------------------------------------------------------


def find_banned_words(text):
    """Return a list of banned words/phrases found in text."""
    return [m.group(0) for m in BANNED_PATTERN.finditer(text)]


def find_null_fields(obj, path=""):
    """Return the paths of every field that is None, e.g. ['evidence.price_check.market_median_inr']."""
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            found += find_null_fields(value, f"{path}.{key}" if path else key)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            found += find_null_fields(value, f"{path}[{i}]")
    elif obj is None:
        found.append(path)
    return found


def find_urls(obj):
    """Return every http(s) link found anywhere inside obj (no duplicates)."""
    urls = []
    if isinstance(obj, dict):
        for value in obj.values():
            urls += find_urls(value)
    elif isinstance(obj, list):
        for value in obj:
            urls += find_urls(value)
    elif isinstance(obj, str) and obj.startswith("http"):
        urls.append(obj)
    return list(dict.fromkeys(urls))


def _numbers(text):
    text = re.sub(r"(?<=\d),(?=\d)", "", text)  # 3,400 -> 3400
    return re.findall(r"\d+(?:\.\d+)?", text)


def build_user_message(payload):
    risk = payload.get("risk", {})
    nulls = find_null_fields(payload)
    no_data = "\n".join(f"- {p}" for p in nulls) if nulls else "- (none)"
    return (
        "DATA (JSON):\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
        + "\n\nFIELDS WITH NO DATA (say 'data unavailable', do not treat as suspicious):\n"
        + no_data
        + f"\n\nQuote exactly: risk score {risk.get('score')} out of 10, "
        f"risk level {risk.get('risk_level')}, confidence {risk.get('confidence')}.\n"
        "Write the report now."
    )


# ---------------------------------------------------------------------------
# 3. Talking to the local LLM
# ---------------------------------------------------------------------------
def _post_json(url, body, timeout=180):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_llm(system_prompt, user_message):
    """Send one chat request to the local model and return its text."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    if LLM_BACKEND == "llamacpp":
        data = _post_json(
            f"{LLAMACPP_URL}/v1/chat/completions",
            {"model": LLM_MODEL, "messages": messages, "temperature": 0.2, "max_tokens": 350},
        )
        return data["choices"][0]["message"]["content"].strip()

    data = _post_json(
        f"{OLLAMA_URL}/api/chat",
        {
            "model": LLM_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 350},
        },
    )
    return data["message"]["content"].strip()


def is_llm_up():
    """True if the local model server answers. Used by tests and the UI."""
    url = f"{LLAMACPP_URL}/health" if LLM_BACKEND == "llamacpp" else f"{OLLAMA_URL}/api/tags"
    try:
        urllib.request.urlopen(url, timeout=3)
        return True
    except Exception:
        return False


def ask_llm_once(payload, extra_note=""):
    """One raw attempt, no checks. Handy for testing the model itself."""
    return call_llm(SYSTEM_PROMPT, build_user_message(payload) + extra_note)


# ---------------------------------------------------------------------------
# 4. Checking the output against our rules
# ---------------------------------------------------------------------------
def validate_report(text, payload):
    """Return a list of problems. An empty list means the report is safe."""
    problems = []
    low = text.lower()
    risk = payload.get("risk", {})

    banned = find_banned_words(text)
    if banned:
        problems.append(f"uses banned words: {banned}")

    if len(text.split()) > MAX_WORDS:
        problems.append(f"too long ({len(text.split())} words, max {MAX_WORDS})")

    if risk.get("score") is not None and str(risk["score"]) not in text:
        problems.append(f"does not quote the exact score {risk['score']}")
    if risk.get("confidence") is not None and str(risk["confidence"]) not in text:
        problems.append(f"does not quote the exact confidence {risk['confidence']}")

    if "risk indicators found" not in low:
        problems.append('missing the phrase "risk indicators found"')
    if "does not prove fraud" not in low:
        problems.append('missing the phrase "does not prove fraud"')
    if "cybercrime.gov.in" not in low:
        problems.append("missing cybercrime.gov.in")

    if find_null_fields(payload) and "unavailable" not in low:
        problems.append('some data is null but the report never says "unavailable"')

    allowed = set(_numbers(json.dumps(payload))) | {"10"}
    invented = [n for n in _numbers(text) if n not in allowed]
    if invented:
        problems.append(f"contains numbers not in the data: {invented}")

    return problems


# ---------------------------------------------------------------------------
# 5. Safe template (used only if the model keeps breaking rules or is down)
# ---------------------------------------------------------------------------
def _short(text, n):
    words = text.split()
    return " ".join(words[:n]) + ("..." if len(words) > n else "")


def _fact_text(value):
    if value is None:
        return "data unavailable"
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            if isinstance(v, (list, tuple)) or (isinstance(v, str) and v.startswith("http")):
                continue  # links are shown as the source, not as a fact
            label = k.replace("_", " ")
            parts.append(f"{label}: unavailable" if v is None else f"{label}: {v}")
        return ", ".join(parts) or "no details"
    return str(value)


def fallback_report(payload):
    risk = payload.get("risk", {})
    evidence = payload.get("evidence", {}) or {}

    # Evidence shape from the data collector (Member 2):
    # {"seller_id", "listing_url", "profile": {...}, "image_match": {...}, "price": {...}}
    sections = [("profile", "Seller profile"), ("image_match", "Image match"), ("price", "Price check")]
    listing_url = evidence.get("listing_url")

    bullets = []
    for key, label in sections:
        value = evidence.get(key)
        line = f"- {label}: {_short(_fact_text(value), 18)}"
        urls = find_urls(value) or ([listing_url] if listing_url else [])
        if urls:
            line += f" (source: {urls[0]})"
        bullets.append(line)

    return (
        "Summary:\n"
        f"Risk score {risk.get('score')} out of 10 ({risk.get('risk_level')}), "
        f"confidence {risk.get('confidence')}. Risk indicators found.\n\n"
        "What we found:\n" + "\n".join(bullets) + "\n\n"
        "What this does not prove:\n"
        "This does not prove fraud. It only shows risk indicators found in the data we could collect.\n\n"
        "What you can do:\n"
        "- Pay by cash on delivery if possible.\n"
        "- Ask the seller for a live video of the product.\n"
        "- Use a protected payment method.\n"
        "- Check reviews outside the seller's own page.\n"
        "- If you lose money, report at cybercrime.gov.in"
    )


# ---------------------------------------------------------------------------
# 6. The main function the web UI will call
# ---------------------------------------------------------------------------
def generate_report(payload, max_tries=2):
    """
    Returns {"text": str, "source": "llm" or "template", "problems": list}
    - "llm": the model's answer passed every check
    - "template": the model failed or was unreachable, so we used the safe template
    """
    extra = ""
    last_problems = []
    for _ in range(max_tries):
        try:
            text = ask_llm_once(payload, extra)
        except Exception as err:  # server down, timeout, bad JSON ...
            last_problems = [f"LLM error: {err}"]
            break
        last_problems = validate_report(text, payload)
        if not last_problems:
            return {"text": text, "source": "llm", "problems": []}
        extra = (
            "\n\nYour last answer broke these rules: "
            + "; ".join(last_problems)
            + ". Rewrite the full report and fix them."
        )

    return {"text": fallback_report(payload), "source": "template", "problems": last_problems}


if __name__ == "__main__":
    from report.sample_payloads import FULL

    result = generate_report(FULL)
    print(f"[source: {result['source']}]")
    if result["problems"]:
        print("[problems:", result["problems"], "]")
    print(result["text"])
