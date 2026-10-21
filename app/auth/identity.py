"""RRW's names for Cordware's trusted identity (segment 21C).

Cordware is the only Easy Auth parser and the only source of the fake
local identity (`cordware/identity.py`). This module keeps the names
RRW's routes, services and tests import, so moving identity to the host
changed none of them.

`get_current_user` is the dependency and takes the request alone;
`resolve_current_user` takes settings too and is never a dependency.
"""

from __future__ import annotations

from cordware.identity import (
    Identity as AuthenticatedUser,
    decode_client_principal,
    extract_claims,
    get_identity as get_current_user,
    resolve_identity as resolve_current_user,
)

__all__ = [
    "AuthenticatedUser",
    "decode_client_principal",
    "extract_claims",
    "get_current_user",
    "resolve_current_user",
]
