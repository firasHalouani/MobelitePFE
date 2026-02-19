import re

DANGEROUS_PATTERNS = [
    r"eval\(",
    r"exec\(",
    r"os\\.system\(",
    r"subprocess\\.Popen\(",
    r"pickle\\.loads\(",
    r"input\("
]


def _classify_severity(pattern: str) -> str:
    p = pattern.lower()
    if "eval" in p:
        return "CRITICAL"
    if "input" in p:
        return "MEDIUM"
    return "HIGH"


def scan_code(code: str):
    findings = []
    lines = code.split("\n")

    for i, line in enumerate(lines):
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, line):
                findings.append({
                    "line": i + 1,
                    "code": line.strip(),
                    "pattern": pattern,
                    "severity": _classify_severity(pattern)
                })

    return findings


def scan_code_with_ai(code: str):
    """Run rule-based scan then enrich findings with AI suggestions when available."""
    findings = scan_code(code)

    # Import here so we don't require OpenAI at module import time
    try:
        from app.services.ai_helper import generate_ai_recommendation, is_ai_available
    except Exception:
        generate_ai_recommendation = None
        is_ai_available = lambda: False

    if is_ai_available() and generate_ai_recommendation:
        # Execute AI recommendations concurrently with a timeout per call to avoid blocking
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
            snippets = [f.get("code", "") for f in findings]
            with ThreadPoolExecutor(max_workers=min(4, max(1, len(snippets)))) as ex:
                futures = {ex.submit(generate_ai_recommendation, s): idx for idx, s in enumerate(snippets)}
                for fut in as_completed(futures):
                    idx = futures[fut]
                    try:
                        res = fut.result(timeout=8)
                        findings[idx]["ai_recommendation"] = res if res else None
                    except FuturesTimeout:
                        findings[idx]["ai_recommendation"] = None
                    except Exception:
                        findings[idx]["ai_recommendation"] = None
        except Exception:
            # Fallback: attempt serial calls with a short timeout
            for f in findings:
                try:
                    snippet = f.get("code", "")
                    f["ai_recommendation"] = generate_ai_recommendation(snippet)
                except Exception:
                    f["ai_recommendation"] = None
    else:
        # Do not attach AI fields when AI is not configured — keep response concise
        pass

    return findings

