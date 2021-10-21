"""Module for managing torrent file parsing.
"""
import hashlib
from math import ceil, floor
from pathlib import Path
from typing import Tuple

import numpy as np
from bencode import decode, decode_torrent, encode_torrent

from .config import BLOCK_SIZE, PEER_ID, ROOT_DIR
from .logger import get_logger
from .utils import read_file

LOG = get_logger(__name__)


class TorrentMD:
    """Parses the torrent file and allows for access to data within.

    Parsed so that single file and multi file torrents have the same
    attributes exposed.

    Parameters
    ----------
    torrent_file_path: Path
        Path obj refering to torrent file
    """

    def __init__(self, torrent_file_path: Path, verbose=True):
        self.torrent_file_path = torrent_file_path
        self._parse_torrent_file(verbose=verbose)

    def _parse_torrent_file(self, verbose=True):
        """Parsing logic common to single & multi file torrents."""
        # logic common to single and multifile torrents
        raw_bytes = read_file(self.torrent_file_path)
        self.torrent_dict = decode_torrent(raw_bytes, encoding="utf8", errors="strict")
        self.torrent_bytes = decode(raw_bytes)
        self.info_hash = hashlib.sha1(
            encode_torrent(self.torrent_dict["info"])
        ).digest()

        # logic specific to single and multifile torrents
        if "files" in self.torrent_dict["info"]:
            self.multi_file = True
            self._parse_multi_file()
        else:
            self.multi_file = False
            self._parse_single_file()

        if verbose:
            self._log_details()

    def _parse_single_file(self):
        """Parsing single file torrent."""
        self.file_count = 1
        self.file_name = self.torrent_dict["info"]["name"]
        self.torrent_length = int(self.torrent_dict["info"]["length"])
        self.piece_count = (
            self.torrent_dict["info"]["length"]
            / self.torrent_dict["info"]["piece length"]
        )

        self.piece_count = ceil(self.piece_count)
        self.blocks = [
            (j, BLOCK_SIZE * i, BLOCK_SIZE)
            for j in range(self.piece_count)
            for i in range(int(self.torrent_dict["info"]["piece length"] / BLOCK_SIZE))
        ]
        pieces = self.torrent_bytes[b"info"][b"pieces"]
        # list of hashes used to validate each piece
        self.piece_hashes = [
            pieces[int(n * 20) : int((n + 1) * 20)] for n in range(self.piece_count)
        ]

    def _parse_multi_file(self):
        """Parsing multi file torrent."""
        pieces = self.torrent_bytes[b"info"][b"pieces"]
        # list of hashes used to validate each piece
        self.piece_hashes = [
            pieces[int(n * 20) : int((n + 1) * 20)]
            for n in range(int(len(pieces) / 20))
        ]

        self.piece_count = int(len(pieces) / 20)

        self.torrent_length = 0
        self.file_count = len(self.torrent_dict["info"]["files"])
        for file_dict in self.torrent_dict["info"]["files"]:
            self.torrent_length += int(file_dict["length"])

        files = self.torrent_dict["info"]["files"]
        file_lens = [f["length"] for f in files]
        self.file_lengths = file_lens
        self.file_paths = [Path("/".join(p)) for p in [f["path"] for f in files]]
        file_cumsum = np.cumsum(file_lens)
        self.file_offsets: Tuple[int, int] = [
            (floor(f / self.piece_length), f % self.piece_length) for f in file_cumsum
        ]

    @property
    def piece_length(self):
        return self.torrent_dict["info"]["piece length"]

    def _log_details(self):
        """Helper method that logs details of parsed file.

        Currently setup to run when `verbose` is passed but can be
        called directly.
        """
        LOG.info(
            f"""
        TORRENT FILE SUMMARY
        --------------------
        announce URL: {self.torrent_dict["announce"]}
        torrent size: (mb) {self.torrent_length/1_000_000}
        piece count: {self.piece_count}
        each piece is same size: {self.torrent_length%self.torrent_dict["info"]["piece length"] == 0}
        piece size: (mb) {self.torrent_dict["info"]["piece length"]/1_000_000}
        piece size: (bytes) {self.torrent_dict["info"]["piece length"]}
        last piece size (bytes): {self.torrent_length%self.torrent_dict["info"]["piece length"]}
        block size: (mb) {BLOCK_SIZE/1_000_000}
        each piece downloaded in (bytes): {self.torrent_dict["info"]["piece length"] / BLOCK_SIZE} 

        Extra details
        -------------
        file_count: {self.file_count}
        """
        )

    def get_handshake(self):
        """Get both handshake dict and byte payload."""
        handshake_dict = {
            "pstrlen": bytes([19]),
            "pstr": "BitTorrent protocol".encode(),
            "reserved": bytes([0] * 8),
            "info_hash": self.info_hash,
            "peer_id": PEER_ID.encode(),
        }
        handshake_payload = b"".join([val for key, val in handshake_dict.items()])
        handshake_payload

        return (handshake_dict, handshake_payload)
