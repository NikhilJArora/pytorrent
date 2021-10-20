"""Holds classes responsible for torrent IO.
"""
import hashlib
from collections import deque
from math import ceil, floor
from typing import List, Tuple

from pytorrent.config import BLOCK_SIZE, ROOT_DIR
from pytorrent.torrent_file import TorrentMD

from .logger import get_logger

LOG = get_logger(__name__)


class PieceManager:
    """Manages IO for all pieces of a given torrent file.

    Builds all pieces and passes them to peers when requested.
    """

    def __init__(self, torrent_md: TorrentMD, writer) -> None:
        self._md = torrent_md
        self.writer = (
            writer  # responsible for providing basic write methods `write_piece`
        )
        self._create_queue()

    def _create_queue(self):
        """Build piece queue.

        Only builds queue with pieces that are not currently downloaded.
        """
        LOG.info(self._md.piece_count)
        self._q = deque([], maxlen=self._md.piece_count)

        curr_pieces = self.writer.curr_pieces()

        whole_piece_count = floor(
            self._md.torrent_length / self._md.torrent_dict["info"]["piece length"]
        )
        blocks = [
            (BLOCK_SIZE * i, BLOCK_SIZE)
            for i in range(
                floor(self._md.torrent_dict["info"]["piece length"] / BLOCK_SIZE)
            )
        ]
        for i in range(whole_piece_count):
            if i in curr_pieces:
                continue
            _piece = Piece(
                i,
                blocks,
                self._md.piece_hashes[i],
                self._md.torrent_dict["info"]["piece length"],
                self.writer,
            )
            self._q.append(_piece)

        irregular_piece = (
            self._md.torrent_length % self._md.torrent_dict["info"]["piece length"]
        )
        # case for adding last piece as different length
        if irregular_piece != 0:
            irregular_ind = whole_piece_count
            if irregular_ind in curr_pieces:
                return
            blocks_irr = [
                (BLOCK_SIZE * i, BLOCK_SIZE)
                for i in range(floor(irregular_piece / BLOCK_SIZE))
            ]
            blocks_irr.append(
                (
                    int(BLOCK_SIZE * floor(irregular_piece / BLOCK_SIZE)),
                    irregular_piece % BLOCK_SIZE,
                )
            )

            _piece = Piece(
                irregular_ind,
                blocks_irr,
                self._md.piece_hashes[irregular_ind],
                irregular_piece,
                self.writer,
            )
            self._q.append(_piece)

    def get_piece(self, bitfield: List[bool]):
        """Get peice from queue.

        Gets piece based on the bitfield you have passed so only gives
        pieces you have access to.
        """
        while True:
            try:
                piece = self._q.popleft()
            except IndexError:
                return None

            if bitfield[piece.index]:
                return piece
            else:
                self._q.append(piece)

    def return_piece(self, piece) -> None:
        """In case Peer cannot successfully get piece data, return piece."""
        self._q.append(piece)


class Piece:
    """Piece that is passed to Peer to be downloaded.

    Built with helper methods abstracting complexity of byte location
    and writing away from Peer.
    """

    def __init__(
        self, index, blocks: Tuple[int, int], piece_hash, length, writer
    ) -> None:
        self.index = index
        self.blocks = blocks
        self.piece_hash = piece_hash
        self._writer = writer
        self.blocks_recieved = 0
        self.length = length
        self._block_data = [None] * len(self.blocks)

    def write_block(self, index, begin, block):
        """Takes the block with index and begin.

        Will take block, validate expected index, begin

        Returns
        -------
        bool
            state of piece download, True means done!
        """
        if index != self.index:
            raise ValueError(
                f"Block sent with incorrect index. expected {self.index} but got {index}"
            )

        if begin % BLOCK_SIZE != 0:
            raise ValueError(
                f"Block begin spot should return 0: begin % BLOCK_SIZE {begin % BLOCK_SIZE}"
            )
        LOG.info(f"Writing {index}, {begin} to block index: {begin/BLOCK_SIZE}")
        self._block_data[int(begin / BLOCK_SIZE)] = block
        self.blocks_recieved += 1
        if self.blocks_recieved == len(self.blocks):
            return self._write_piece()
        else:
            return False

    def _write_piece(self):
        """Write bytes once block fully populated.

        Private method only meant to be called by self.
        """
        piece_bytes = b"".join(self._block_data)
        if self._validate_piece(piece_bytes):
            self.piece_bytes = piece_bytes
            self._writer.write_piece(self)
            return True
        else:
            return False

    def _validate_piece(self, piece_bytes: bytes):
        """Validate piece_bytes with piece hash and length."""
        if len(piece_bytes) != self.length:
            LOG.error(
                f"Piece {self.index}: bytes not the expected length ({self.length}). Got {len(piece_bytes)}"
            )
            return False

        curr_piece_hash = hashlib.sha1(piece_bytes).digest()
        if curr_piece_hash != self.piece_hash:
            LOG.error(
                f"Piece {self.index}: calculated piece hash does not match {curr_piece_hash} does not match expected {self.piece_hash}"
            )
            return False

        return True


class FileWriter:
    """Class repsonsible for interfacing with file system.

    Currently capable of writing piece files.
    WIP regarding logic to write files based on pieces.
    """

    def __init__(self, torrent_md, root_path=None) -> None:

        if not root_path:
            root_path = ROOT_DIR
        torr_info_name = torrent_md.torrent_dict["info"]["name"]
        self.torr_write_dir = (
            root_path / "".join(ch for ch in torr_info_name if ch.isalnum()).lower()
        )
        self.piece_dir = self.torr_write_dir / "piece_dir"
        self.piece_dir.mkdir(parents=True, exist_ok=True)

    def curr_pieces(self) -> set:
        """Returns set of indicies currently downloaded."""
        return {int(f.stem) for f in self.piece_dir.glob("*.piece")}

    def write_piece(self, piece: Piece):
        """"""
        if not isinstance(piece.piece_bytes, bytes):
            raise TypeError(
                f"Expected piece.piece_bytes of type bytes, got {type(piece.piece_bytes)}"
            )

        piece_path = self.piece_dir / f"{piece.index}.piece"
        FileWriter._write_bytes(piece.piece_bytes, piece_path)

    @staticmethod
    def _write_bytes(data: bytes, file_path):
        assert isinstance(data, bytes)
        with open(file_path, "wb") as f:
            f.write(data)
