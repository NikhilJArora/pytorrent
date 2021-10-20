#!/usr/bin/env python

"""Tests for the classes within the `connections` module."""

import pytest
from pathlib import Path

from pytorrent.connections import Peer, Tracker
from pytorrent.torrent_io import FileWriter, PieceManager

from pytorrent.torrent_file import TorrentMD
from pytorrent.config import BLOCK_SIZE, PEER_ID
from pytorrent.twisted_client import PeerClientFactory
from pytorrent import cli

DATA_PATH = Path(__file__).parent.resolve() / "data"
TORRENT_PATH = DATA_PATH / "debian-10.10.0-amd64-netinst.iso.torrent"


def test_tracker_get_peers():
    """Test tracker can be reached and peers return
    """
    test_announce_url = "http://bttracker.debian.org:6969/announce"
    test_info_hash = b'\xa7\x80(=8\xf1@\xe4\x06[%\xca\xe9\x19^\t\xd0\x13_\xc5'
    test_peer_id = "08351903611630915380"
    test_length = 352321536
    test_tracker = Tracker(test_announce_url, test_info_hash, test_peer_id, test_length)
    test_peers = test_tracker.get_peers()
    
    assert isinstance(test_peers, list)
    assert len(test_peers) > 0

def test_peer_init():
    """Test can init peer connection using Twisted reactor.
    """
    test_peer_ls = [('201.37.65.80', 50000), ('142.163.87.141', 53000), ('91.236.103.43', 60908)]
    torrent_md = TorrentMD(TORRENT_PATH)
    file_writer = FileWriter(torrent_md)
    piece_manager = PieceManager(torrent_md, file_writer)    
    
    from twisted.internet import reactor
    
    peer = Peer(test_peer_ls[10], reactor, PeerClientFactory, torrent_md.get_handshake(), piece_manager, file_writer)
    