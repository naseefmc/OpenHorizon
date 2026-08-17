"""One-click "search this name on Google Images" — used from Nearby,
History, Ports, and Airports wherever a vessel/aircraft name is shown, so
identifying an unfamiliar contact doesn't require manually retyping its
name into a browser. Image search rather than plain web search since the
actual use case is "what does this thing look like" — appending a
vessel/aircraft keyword when the caller knows the target's kind keeps a
bare name (e.g. a common vessel name) from pulling in unrelated results.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


# "aircraft" is the internal kind value used throughout the app (filters,
# roles, etc.); "flight" is what actually gets searched for, since it
# returns more relevant image results than the more generic "aircraft".
_SEARCH_KEYWORDS = {"aircraft": "flight"}


def open_google_image_search(name: str, kind: str | None = None) -> None:
    name = (name or "").strip()
    if not name:
        return
    keyword = _SEARCH_KEYWORDS.get(kind, kind) if kind else None
    query = f"{name} {keyword}" if keyword else name
    QDesktopServices.openUrl(QUrl(f"https://www.google.com/search?tbm=isch&q={quote_plus(query)}"))
