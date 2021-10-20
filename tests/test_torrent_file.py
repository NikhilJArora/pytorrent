"""Test torrent parsing logic."""

from pathlib import Path
import pytest

from pytorrent.torrent_file import TorrentMD
from pytorrent.torrent_io import PieceManager, FileWriter
from pytorrent.config import BLOCK_SIZE
from pytorrent import cli

DATA_PATH = Path(__file__).parent.resolve() / "data"
TORRENT_PATH = DATA_PATH / "debian-10.10.0-amd64-netinst.iso.torrent"
TORRENT_PATH_MULTI = DATA_PATH / "Doom II_ Delta-Q-Delta.torrent"



def test_torrent_parse_file():
    """Test parser is able to properly parse single file torrent."""
    
    torrent_md = TorrentMD(TORRENT_PATH)
    assert hasattr(torrent_md, "torrent_dict")
    assert hasattr(torrent_md, "torrent_bytes")
    assert torrent_md.piece_count == len(torrent_md.piece_hashes)
    hs_dict, hs_payload = torrent_md.get_handshake()
    assert len(hs_dict["peer_id"]) == 20
    assert "info_hash" in hs_dict
    assert hs_dict["info_hash"] in hs_payload
    for hash in torrent_md.piece_hashes:
        assert len(hash) == 20
    assert len(torrent_md.blocks) == torrent_md.piece_count* int(torrent_md.torrent_dict["info"]["piece length"] / BLOCK_SIZE)


def test_torrent_parse_multifile():
    """Test parser is able to properly parse multi-file torrent."""
    
    torrent_md = TorrentMD(TORRENT_PATH_MULTI)
    assert hasattr(torrent_md, "torrent_dict")
    assert hasattr(torrent_md, "torrent_bytes")
    assert torrent_md.piece_count == len(torrent_md.piece_hashes)
    hs_dict, hs_payload = torrent_md.get_handshake()
    assert len(hs_dict["peer_id"]) == 20
    assert "info_hash" in hs_dict
    assert hs_dict["info_hash"] in hs_payload
    for hash in torrent_md.piece_hashes:
        assert len(hash) == 20


def test_building_torrent_piece_queue_multifile():
    """Test building piece queue from multi-file torrent."""
    
    torrent_md = TorrentMD(TORRENT_PATH_MULTI)
    assert hasattr(torrent_md, "torrent_dict")
    assert hasattr(torrent_md, "torrent_bytes")
    assert torrent_md.piece_count == len(torrent_md.piece_hashes)
    hs_dict, hs_payload = torrent_md.get_handshake()
    assert len(hs_dict["peer_id"]) == 20
    assert "info_hash" in hs_dict
    assert hs_dict["info_hash"] in hs_payload
    for hash in torrent_md.piece_hashes:
        assert len(hash) == 20
    
    fw = FileWriter(torrent_md)
    pm = PieceManager(torrent_md, fw)
    assert len(pm._q) == torrent_md.piece_count
    


