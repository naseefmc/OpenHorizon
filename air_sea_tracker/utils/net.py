"""macOS asyncio TCP_NODELAY workaround.

On macOS, `asyncio`'s `_SelectorSocketTransport` unconditionally calls
`setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)` on every new TCP connection.
When the connection goes through certain network paths (VPNs, Little
Snitch/LuLu-style filters, iCloud Private Relay, some corporate proxies)
that setsockopt call raises `OSError: [Errno 22] Invalid argument` —
this is a real macOS/CPython interaction, not a bug in this app or in
aiohttp, and it isn't specific to IPv4 vs IPv6. TCP_NODELAY is a pure
performance tweak (disables Nagle's algorithm); failing to set it is
harmless, but asyncio doesn't catch the error, so it kills the whole
connection attempt. Patched to log-and-ignore instead of raising.
"""

from __future__ import annotations

import asyncio.base_events as _base_events
import logging

logger = logging.getLogger(__name__)

_original_set_nodelay = _base_events._set_nodelay
_patched = False


def _safe_set_nodelay(sock) -> None:
    try:
        _original_set_nodelay(sock)
    except OSError:
        logger.debug("TCP_NODELAY unsupported on this socket path, ignoring", exc_info=True)


def patch_tcp_nodelay() -> None:
    global _patched
    if _patched:
        return
    _base_events._set_nodelay = _safe_set_nodelay
    _patched = True
