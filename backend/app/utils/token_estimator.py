from math import ceil


def estimate_tokens(*chunks: str) -> int:
    text = "\n".join(chunk for chunk in chunks if chunk)
    return ceil(len(text) / 4) if text else 0

