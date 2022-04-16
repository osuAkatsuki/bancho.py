from __future__ import annotations

# TODO: move these out so we can delete this file

bcrypt: dict[bytes, bytes] = {}  # {bcrypt: md5, ...}
unsubmitted: set[str] = set()  # {md5, ...}
needs_update: set[str] = set()  # {md5, ...}
