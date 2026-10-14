"""Small byte patches for bugs in the game client that the server cannot work around."""
import functools
import zlib

# QuestTree.checkPlacement starts with "fits = false" and only sets it to true while looping over the mini series
# buildings that are already on the island. For the first one there are none, so no position ever fits and the
# client puts the building at 0,0, outside of the map, where the mini series cannot be opened. Start with true; the
# check before the loop still rejects positions that are taken by another object.
#   pushnan; setlocal 12 .. setlocal 15; pushfalse (0x27) -> pushtrue (0x26); setlocal 5
PATCHES = [
    (bytes.fromhex("28630c28630d28630e28630f276305"), bytes.fromhex("28630c28630d28630e28630f266305")),
]


@functools.lru_cache(maxsize=4)
def patch_client(data):
    """Returns the swf with the patches applied, or unchanged if it is not a version they fit."""
    if data[:3] not in (b"CWS", b"FWS"):
        return data
    body = zlib.decompress(data[8:]) if data[:3] == b"CWS" else data[8:]
    for old, new in PATCHES:
        if body.count(old) != 1:
            print("Client patch does not fit this client, skipped", old.hex())
            continue
        body = body.replace(old, new)
    if data[:3] == b"CWS":
        return data[:8] + zlib.compress(body, 9)
    return data[:8] + body
