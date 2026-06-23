from __future__ import annotations

class Pkcs7Padding:
    def __init__(self, block_size: int) -> None: ...

class RijndaelCbc:
    def __init__(
        self,
        *,
        key: bytes,
        iv: bytes,
        padding: Pkcs7Padding,
        block_size: int,
    ) -> None: ...
    def encrypt(self, plaintext: bytes) -> bytes: ...
    def decrypt(self, ciphertext: bytes) -> bytes: ...
