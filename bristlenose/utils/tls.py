"""TLS trust for the stdlib's ``urllib`` calls.

``urllib`` verifies against the system store as it stands. On a fresh Windows
machine that store lacks roots which Windows fetches only when a CryptoAPI
client (curl.exe, a browser) asks for them, so Python alone fails with
CERTIFICATE_VERIFY_FAILED. Measured 5 Oct 2026 on a new Windows Server 2025 box:
api.anthropic.com and api.openai.com both chain to Google Trust Services, absent
until something else had touched the host. Doctor called the network down, and
``configure`` could not validate a good key.

The context trusts the system store *and* certifi's bundle. The system store is
kept, not replaced, because it is where a corporate TLS-inspecting proxy's root
lives. httpx (the LLM SDKs) already ships certifi's bundle, which is why the
analysis calls themselves were unaffected.
"""

from __future__ import annotations

import ssl


def https_context() -> ssl.SSLContext:
    """A default-verifying context with certifi's roots added to the system's."""
    context = ssl.create_default_context()
    try:
        import certifi  # installed with httpx, which every provider SDK requires
    except ImportError:
        return context
    try:
        context.load_verify_locations(cafile=certifi.where())
    except (OSError, ssl.SSLError):
        pass
    return context
