from __future__ import annotations

def make_short(default_limit):
    def short(value, limit=default_limit):
        text = str(value or "")
        if len(text) <= limit:
            return text
        return text[:limit] + "\n...[обрезано]"

    return short

