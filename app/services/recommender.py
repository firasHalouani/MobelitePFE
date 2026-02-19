def generate_recommendation(finding):
    """Return an AI-generated recommendation for the finding.

    If the AI client is not configured or an error occurs, return None so the
    caller does not attach a static recommendation.
    """
    try:
        from app.services.ai_helper import generate_ai_recommendation, is_ai_available
    except Exception:
        return None

    # Only use AI-generated recommendations. If AI is not configured, return None.
    try:
        if not (is_ai_available() and generate_ai_recommendation):
            return None
    except Exception:
        return None

    try:
        snippet = finding.get("code", "")
        # Run AI call in a short-lived thread with timeout to avoid blocking the request
        try:
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(generate_ai_recommendation, snippet)
                try:
                    ai_resp = future.result(timeout=90)
                except FuturesTimeout:
                    return None
        except Exception:
            # If concurrency primitives unavailable, fall back to direct call
            ai_resp = generate_ai_recommendation(snippet)

        return ai_resp if ai_resp else None
    except Exception:
        return None
