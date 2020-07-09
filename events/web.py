from typing import Dict, Tuple

Headers = Tuple[str]
GET_Params = Dict[str, str]

# For /web/ requests, we send the
# data directly back in the event.

# URI: /osu-osz2-getscores.php
def getScores(headers: Headers, params: GET_Params) -> bytes:
    ret = bytearray()
    ...
    return bytes(ret)
