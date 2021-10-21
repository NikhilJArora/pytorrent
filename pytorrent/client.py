"""PyTorrent client entry-point."""
from os import name
from pathlib import Path
from typing import Optional, Union

from twisted.internet import reactor, task

from pytorrent.config import PEER_ID
from pytorrent.connections import Peer, Tracker
from pytorrent.logger import get_logger
from pytorrent.torrent_file import TorrentMD
from pytorrent.torrent_io import FileWriter, PieceManager
from pytorrent.twisted_client import PeerClientFactory

LOG = get_logger(__name__)


class PyTorrent:
    """PyTorrent class which takes a torrent filepath and downloads it.

    Parameters
    ----------
    torrent_file: str or Path
        file path of torrent file to download.
    """

    def __init__(self, torrent_file: Union[str, Path]):
        # check type of torrent
        self.torrent = Path(torrent_file)
        self.torrent_md = TorrentMD(self.torrent)
        self.file_writer = FileWriter(self.torrent_md)
        self.piece_manager = PieceManager(self.torrent_md, self.file_writer)

    def start(self):
        """Run torrent download.

        Run will result in initializing connection with Tracker, getting
        peer list, initializing peer connections, registering
        them with our Twisted event loop (reactor) and running the
        loop.
        """
        tracker = Tracker(
            self.torrent_md.torrent_dict["announce"],
            self.torrent_md.info_hash,
            PEER_ID,
            self.torrent_md.torrent_length,
        )
        self.peer_ip_ports = tracker.get_peers()
        LOG.info(self.peer_ip_ports)

        peers = []
        for i in range(len(self.peer_ip_ports)):
            peer = Peer(
                self.peer_ip_ports[i],
                reactor,
                PeerClientFactory,
                self.torrent_md.get_handshake(),
                self.piece_manager,
                self.file_writer,
            )
            peers.append(peer)

        reactor.run()

    def create_files(self, output_location: Optional[Union[str, Path]] = None):
        """Takes downloaded pieces and creates files.

        Creation of files expects that each piece is downloaded.
        """
        self.file_writer.write_files(output_location)


if __name__ == "__main__":
    # TEMP: will refactor into proper CLI - ref to test data for now
    DATA_PATH = Path(__file__).parent.parent.resolve() / "tests" / "data"
    TORRENT_PATH = DATA_PATH / "debian-10.10.0-amd64-netinst.iso.torrent"
    # TORRENT_PATH = DATA_PATH / "Doom II_ Delta-Q-Delta.torrent"

    pt = PyTorrent(TORRENT_PATH)
    pt.start()
    pt.create_files()
