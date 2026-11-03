import os
import zlib

import client_patches

SWF = os.path.join(os.path.dirname(__file__), "..", "assets", "ZGame.109338_tracer2.swf")


def test_hook_placement_patch_applies_to_the_served_client():
    with open(SWF, "rb") as f:
        data = f.read()

    patched = client_patches.patch_client(data)

    body = zlib.decompress(patched[8:])
    old, new = client_patches.PATCHES[0]
    assert body.count(new) == 1 and body.count(old) == 0
    assert patched[:8] == data[:8]  # header and uncompressed length unchanged
    assert len(body) == len(zlib.decompress(data[8:]))


def test_unknown_data_is_left_alone():
    assert client_patches.patch_client(b"not a swf") == b"not a swf"
