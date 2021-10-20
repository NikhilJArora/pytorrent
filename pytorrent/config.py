"""Module to define all configurable constants."""

import time
from pathlib import Path

BLOCK_SIZE = pow(2, 14)

PEER_ID = f"{str(round(time.time()))[::-1]}{str(round(time.time()))}"

assert len(PEER_ID) == 20

# data location
ROOT_DIR = Path("~/pytorrent_data").expanduser()
ROOT_DIR.mkdir(exist_ok=True)
