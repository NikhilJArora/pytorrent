"""Holds classes responsible for torrent IO.
"""
import hashlib
from collections import deque
from math import ceil, floor
from pathlib import Path
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

    def __init__(self, torrent_md: TorrentMD, root_path=None) -> None:

        if not root_path:
            root_path = ROOT_DIR
        self._md = torrent_md
        torr_info_name = self._md.torrent_dict["info"]["name"]
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
    def _write_bytes(data: bytes, file_path, mode="wb"):
        """Set mode to "ab" incase you want to append to file."""
        assert isinstance(data, bytes)
        with open(file_path, mode) as f:
            f.write(data)

    @staticmethod
    def _read_bytes(file_path, mode="rb"):
        """read bytes from file."""
        with open(file_path, mode) as f:
            return f.read()

    def write_files(self, output_location=None):
        """Writes files to output_location.

        Assumes pieces are downloaded.
        """
        curr_pieces = self.curr_pieces()
        if len(curr_pieces) != self._md.piece_count:
            raise IndexError(
                f"Unable to create file/files since missing {self.self._md.piece_count - len(curr_pieces)} pieces."
            )

        if output_location is None:
            self.file_dir = self.torr_write_dir / "files"
            self.file_dir.mkdir(exist_ok=True)
        else:
            self.file_dir = Path(output_location)
            self.file_dir.mkdir(parents=True, exist_ok=True)

        if self._md.file_count > 1:
            self._write_multi_files()
        else:
            self._write_file()

    def _write_file(self):
        """Writes single file to ``self.file_dir`` from pieces in ``self.piece_dir``."""
        abs_file_path = self.file_dir / Path(self._md.file_name)
        abs_file_path.unlink(missing_ok=True)
        if abs_file_path.exists():
            raise RuntimeError("Expected file would be deleted.")
        abs_file_path.parent.mkdir(parents=True, exist_ok=True)
        abs_file_path.touch()

        for piece_ind in range(self._md.piece_count):
            pce_path = self.piece_dir / f"{piece_ind}.piece"
            FileWriter._write_bytes(pce_path.read_bytes(), abs_file_path, mode="ab")

    def _write_multi_files(self):
        """Writes files to ``self.file_dir`` from pieces in ``self.piece_dir``."""

        file_offsets = self._md.file_offsets
        file_paths = self._md.file_paths
        pce_length = self._md.piece_length

        h_pce_ind, h_byte_ind = (0, 0)
        for i, (file_path, (t_pce_ind, t_byte_ind)) in enumerate(
            zip(file_paths, file_offsets)
        ):
            abs_file_path = self.file_dir / file_path
            abs_file_path.unlink(missing_ok=True)
            if abs_file_path.exists():
                raise RuntimeError("Expected file would be deleted.")
            abs_file_path.parent.mkdir(parents=True, exist_ok=True)
            abs_file_path.touch()
            LOG.info(
                f"Working on {abs_file_path}, \nexpected size: {self._md.file_lengths[i]}"
                f"\n{(h_pce_ind, h_byte_ind)} to {(t_pce_ind, t_byte_ind)}"
            )
            if h_pce_ind == t_pce_ind:
                # parsing from within single piece
                LOG.info(f"Parsing from within single piece")
                LOG.debug(
                    f"Working on {abs_file_path}, expected size: {self._md.file_lengths[i]}"
                )
                pce_path = self.piece_dir / f"{h_pce_ind}.piece"
                pce_bytes = pce_path.read_bytes()
                file_bytes = pce_bytes[h_byte_ind:t_byte_ind]
                abs_file_path.write_bytes(file_bytes)
            else:
                # head and tail span over multiple pieces
                # have to loop over range of files, slicing first, middle and last differently
                for pce_ind in range(h_pce_ind, t_pce_ind + 1):
                    LOG.debug(f"{pce_ind}")
                    if pce_ind == h_pce_ind:
                        # slice off start off file
                        LOG.debug(f"First piece: {pce_ind}")
                        pce_path = self.piece_dir / f"{pce_ind}.piece"
                        pce_bytes = pce_path.read_bytes()
                        file_bytes = pce_bytes[h_byte_ind:]
                        LOG.debug(f"len(file_bytes): {len(file_bytes)}")
                        FileWriter._write_bytes(file_bytes, abs_file_path, mode="ab")
                    elif pce_ind == t_pce_ind:
                        # slice off tail of file for last piece
                        LOG.debug(f"Last piece: {pce_ind}")
                        pce_path = self.piece_dir / f"{pce_ind}.piece"
                        pce_bytes = pce_path.read_bytes()
                        file_bytes = pce_bytes[:t_byte_ind]
                        LOG.debug(f"len(file_bytes): {len(file_bytes)}")
                        FileWriter._write_bytes(file_bytes, abs_file_path, mode="ab")
                    else:
                        # grab all bytes for pieces in middle of file
                        LOG.debug(f"Middle piece: {pce_ind}")
                        LOG.debug(f"len(pce_bytes): {len(pce_bytes)}")
                        pce_path = self.piece_dir / f"{pce_ind}.piece"
                        pce_bytes = pce_path.read_bytes()
                        LOG.debug(f"len(file_bytes): {len(pce_bytes)}")
                        FileWriter._write_bytes(pce_bytes, abs_file_path, mode="ab")

            full_bytes = abs_file_path.read_bytes()
            if len(full_bytes) not in set(self._md.file_lengths):
                raise ValueError(
                    f"Output file: {abs_file_path} is the wrong number of bytes."
                )

            h_pce_ind, h_byte_ind = t_pce_ind, t_byte_ind
