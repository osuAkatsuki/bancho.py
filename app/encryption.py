from __future__ import annotations

from base64 import b64decode
from base64 import b64encode

from py3rijndael import Pkcs7Padding
from py3rijndael import RijndaelCbc


def encrypt_score_aes_data(
    # to encode
    score_data: list[str],
    client_hash: str,
    # used for encoding
    iv_b64: bytes,
    osu_version: str,
) -> tuple[bytes, bytes]:
    """Encrypt the score data to base64."""
    # TODO: perhaps this should return TypedDict?

    # attempt to encrypt score data
    aes = RijndaelCbc(
        key=f"osu!-scoreburgr---------{osu_version}".encode(),
        iv=b64decode(iv_b64),
        padding=Pkcs7Padding(32),
        block_size=32,
    )

    score_data_joined = ":".join(score_data)
    score_data_b64 = b64encode(aes.encrypt(score_data_joined.encode()))
    client_hash_b64 = b64encode(aes.encrypt(client_hash.encode()))

    return score_data_b64, client_hash_b64


def decrypt_score_aes_data(
    # to decode
    score_data_b64: bytes,
    client_hash_b64: bytes,
    # used for decoding
    iv_b64: bytes,
    osu_version: str,
) -> tuple[list[str], str]:
    """Decrypt the base64'ed score data."""
    # TODO: perhaps this should return TypedDict?

    # attempt to decrypt score data
    aes = RijndaelCbc(
        key=f"osu!-scoreburgr---------{osu_version}".encode(),
        iv=b64decode(iv_b64),
        padding=Pkcs7Padding(32),
        block_size=32,
    )

    score_data = aes.decrypt(b64decode(score_data_b64)).decode().split(":")
    client_hash_decoded = aes.decrypt(b64decode(client_hash_b64)).decode()

    # score data is delimited by colons (:).
    return score_data, client_hash_decoded
