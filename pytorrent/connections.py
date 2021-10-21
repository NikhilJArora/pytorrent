"""Module containing Tracker and Peer classes."""

import socket
import struct
import time
from enum import Enum
from typing import Optional, Tuple

import requests
from bencode import decode
from twisted.internet.error import ReactorNotRunning

from .logger import get_logger
from .msg_handler import MsgHandler

LOG = get_logger(__name__)


class Tracker:
    """Tracker connection.

    Makes request to tracker URL and retrieves parsed peers. Currently only have
    support for http urls.

    Parameters
    ----------

    Returns
    -------

    """

    def __init__(
        self, announce_url: str, info_hash: bytes, peer_id: str, torrent_length: int
    ):

        if "http" in announce_url:
            self.announce_url = announce_url
        else:
            LOG.error(
                "Currently only support http trackers." "Got {announce_url} instead."
            )
            raise TypeError(
                "Currently only support http trackers." "Got {announce_url} instead."
            )

        if len(info_hash) != 20:
            raise ValueError(
                f"Required format of info_hash is 20-byte SHA1. Got {len(info_hash)}"
            )
        if len(peer_id) != 20:
            raise ValueError(
                f"Required length of peer_id is 20-byte string. Got {len(peer_id)}"
            )

        self.info_hash = info_hash
        self.peer_id = peer_id
        self.torrent_length = torrent_length

        self._set_url_params()

        self.interval = None
        self.last_req = None

    def _set_url_params(self):
        """Create the URL params dict but also validate inputs"""
        self.url_params = {
            "info_hash": self.info_hash,
            "peer_id": self.peer_id,
            "port": "6881",
            "uploaded": "0",
            "downloaded": "0",
            "left": str(self.torrent_length),
            "compact": "1",
        }

        LOG.info(self.url_params)

    def get_peers(self):
        """Establish connection with tracker and get list of peers.

        Note: could refactor this approach to refresh peers in a
        seperate thread that sleeps the interval time once its set.

        Returns
        -------
        list of tuples
            each peer tuple contains ("I.P" <str>, port <int>)
        """
        # NOTE: might what to rethink this approach
        if self.last_req and self.interval:
            time_passed = int(time.time() - self.last_req)
            if time_passed < self.interval:
                LOG.info(
                    "Unable to refresh peers since time_passed < self.interval"
                    f" ({time_passed} < {self.interval})"
                )
                return self.latest_peers

        resp = requests.get(
            url=self.announce_url,
            params=self.url_params,
        )
        resp.raise_for_status()
        resp_dict = decode(resp.content)
        self.interval = resp_dict[b"interval"]
        self.last_req = time.time()
        self.latest_peers = _format_peers(resp_dict[b"peers"])
        return self.latest_peers

    def get_handshake():
        """Generate handshake payload"""
        pass


def _format_peers(raw_peers: str):
    """Helper func to slice peer string into peer list.

    Expecting compact tracker response format with 6 bytes per peer.
    The first four bytes are the host (in network byte order), the last
    two bytes are the port (again in network byte order).

    Parameters
    ----------
    raw_peers: str
        raw byte string from the final model

    Returns
    -------
    list of tuples
        each peer tuple contains ("I.P" <str>, port <int>)
    """
    peer_list = list()
    for tail in range(6, len(raw_peers) + 1, 6):
        ip_head = tail - 6
        port_head = tail - 2
        ip_address = socket.inet_ntoa(raw_peers[ip_head:port_head])
        port = struct.unpack(">H", raw_peers[port_head:tail])[0]
        peer_list.append((ip_address, port))
    return peer_list


class Peer:
    """Peer application logic.

    Holds application specific logic related to the peer and msg transfer
    state. There should be one instance created per Peer. Currently we expect
    this will be used with ``twisted.internet.protocol.Protocol`` to handle
    application logic of connectionMade, dataReceived and connectionLost
    events. Also resposible for working with piece_manager dequeue a
    piece when ready to request from Peer.
    """

    class PeerState(Enum):
        CONNECTION_PENDING = 0  # allow connection made event
        HANDSHAKE_PENDING = 1  # allow parse of handshake
        BITFIELD_PARSING = 2  # allow parse of either bitfield or have msgs
        REQUEST_PASSING = 3  # allow parse of either bitfield or have msgs

    def __init__(
        self,
        address: Tuple,
        reactor,
        protocal_factory,
        handshake_data,
        piece_manager,
        writer,
        is_client=True,
    ):
        self._handshake_dict, self._handshake_payload = handshake_data
        self.is_client = is_client  # determines what side of the wire peer is on
        self._state = self.PeerState.CONNECTION_PENDING
        self.transport = None
        self._peer_state = {
            "peer_choking": True,
            "am_interested": False,
            # Static for now since only support requesting from peer
            "am_choking": True,
            "peer_interested": False,
        }
        self._piece_manager = piece_manager
        self._writer = writer
        self.host, self.port = address
        self._bitfield = None
        self._piece = None  # will be set by calling `self._get_piece()`
        self.incomplete_msg: Optional[bytes] = None
        LOG.info(f"Current peer connecting to {self.host}, {self.port}")
        self._reactor = reactor
        self._reactor.connectTCP(self.host, self.port, protocal_factory(self))
        # connection made event - update state to CONNECTION_MADE and send handshake

    def _set_bitfield(self, bitfield: dict = None, have: dict = None) -> None:
        """Set `self._bitfield` based on either bitfield or have msg.

        Parameters
        ----------
        bitfield: dict, optional
            payload with `bitfield` key used
        have: dict, optional
            payload with `piece_index` key refering the the

        Returns
        -------
        None

        Side effects
        ------------
        _bitfield : list
            mutable boolean array used to ref what pieces connected peer has
        """
        if bitfield:
            self._bitfield = bitfield["bitfield"]
        elif have:
            self._bitfield[have["piece_index"]] = True
        else:
            LOG.error("Must pass either bitfield & have msg.")
            raise KeyError("Must pass either bitfield & have msg.")

    def _get_piece(self):
        """Grab ``Piece`` object from queue.

        In case of None, assume no more pieces pending and
        closes the connection with peer.
        """
        if self._piece is None:
            piece = self._piece_manager.get_piece(self._bitfield)
            self._piece = piece
        return self._piece

    def send_handshake(self):
        """Called on successful connection ``Protocol.connectionMade``.

        Returns
        -------
        bytes handshake payload

        Side effects
        ------------
        self._state: self.PeerState
            set state to `self.PeerState.HANDSHAKE_PENDING` once called
        """
        self._state = self.PeerState.HANDSHAKE_PENDING
        # send our handshake as soon as peer connected
        self.transport.write(self._handshake_payload)

    def validate_handshake(self, data):
        """Called on successful connection ``Protocol.connectionMade``.

        Parameters
        ----------
        data: bytes
            raw byte payload of incoming peer handshake
        Returns
        -------
        bool
            indicating if incoming handshake is formed correctly and for the
            correct torrent
        """
        if self._handshake_dict["info_hash"] in data and len(data) == len(
            self._handshake_payload
        ):
            return True
        else:
            if self._handshake_dict["info_hash"] not in data:
                LOG.error(
                    f"{self.host}, {self.port}: Missing corrent info_hash {self._handshake_dict['info_hash']}"
                )
            if len(data) != len(self._handshake_payload):
                LOG.error(
                    f"{self.host}, {self.port}: Data passed incorrect length {len(data)} != {len(self._handshake_payload)}"
                )
            return False

    def dataReceived(self, data):
        """Peer application logic related dataReceived.

        Peer application logic related to
        ``twisted.internet.protocol.Protocol.dataReceived``. Will also handle
        returning response bytes.

        Parameters
        ----------
        data: bytes
            packed payload to be sent to connected peer in response

        Returns
        -------
        bytes
            packed response bytes
        """
        if self.incomplete_msg:
            data = self.incomplete_msg + data
            self.incomplete_msg = None

        LOG.debug(f"{self.host}, {self.port}: {data[0:10]}, len: {len(data)}")
        # handshake handling block
        if self._state == self.PeerState.HANDSHAKE_PENDING:
            LOG.info(
                f"{self.host}, {self.port}: Current vs expected handshake payload {len(data)} vs {len(self._handshake_payload)}"
            )
            if len(data) > len(self._handshake_payload):
                handshake_data, next_msg_raw_data = (
                    data[: len(self._handshake_payload)],
                    data[len(self._handshake_payload) :],
                )
                LOG.info(
                    f"{self.host}, {self.port}: {handshake_data}, {next_msg_raw_data}"
                )
            else:
                handshake_data, next_msg_raw_data = data, None
            handshake_valid = self.validate_handshake(handshake_data)
            if handshake_valid:
                LOG.info(
                    f"{self.host}, {self.port}: Peer sent valid handshake, updating state from {self._state} to {self.PeerState.BITFIELD_PARSING}."
                )
                self._state = self.PeerState.BITFIELD_PARSING
                if next_msg_raw_data:
                    self.dataReceived(next_msg_raw_data)
            else:
                LOG.info(
                    f"{self.host}, {self.port}: Peer sent invalid handshake, closing connection."
                )
                self.loseConnection(f"{self.host}, {self.port}: handshake invalid")

        # data handling in any other states
        else:
            msg = MsgHandler(data)
            if msg.is_incomplete:
                self.incomplete_msg = data
                self.transport.write(msg.pack_msg("keep-alive"))
                return
            resp = self.evaluate_msg(msg)
            if resp:
                LOG.info(
                    f"{self.host}, {self.port}: Writing the following payload {resp}"
                )
                self.transport.write(resp)

            if msg.next_msg_raw_data:
                self.dataReceived(msg.next_msg_raw_data)

    def evaluate_msg(self, msg: MsgHandler):
        """Take parsed msg and decide how to handle it based on State.

        Evaluates the combination of msg and state and decides how to update
        the state of our current peer and how it respond if relavent.

        Parameters
        ----------
        msg: MsgHandler
            msg object with parsed msg and packing/unpacking helper methods.

        Returns
        -------
        bytes
            packed msg payload based on msg and state
        """
        LOG.info(
            f"{self.host}, {self.port}: Following msg recieved '{msg.msg_name}', state: {self._state}"
        )
        if msg.msg_name == "keep-alive" or msg.msg_name is None:
            LOG.info("Peer sent keep-alive.")
            return msg.pack_msg("keep-alive")

        if self._state == self.PeerState.BITFIELD_PARSING:
            if msg.msg_name == "bitfield":
                self._set_bitfield(bitfield=msg.msg_payload_parsed)
                LOG.info(
                    f"{self.host}, {self.port}: parsed bitfield which is now set to: ({len(self._bitfield)})"
                )
                self._peer_state["am_interested"] = True
                self._peer_state["am_choking"] = True
                self._state = self.PeerState.REQUEST_PASSING
                return msg.pack_msg("interested")
            elif msg.msg_name == "have":
                self._set_bitfield(have=msg.msg_payload_parsed)
                LOG.info(f"{self.host}, {self.port}: parsed have msg.")
            elif msg.msg_name == "choke":
                # telling me that its time to review bitfield and decide if Im going to need anything
                if self._get_piece():
                    self._peer_state["am_interested"] = True
                    self._peer_state["am_choking"] = True
                    return msg.pack_msg("interested")
                else:
                    LOG.info("Unable to find any needed pieces from peer")
                    return msg.pack_msg("not interested")
            elif msg.msg_name == "unchoke":
                self._peer_state["am_choking"] = False
                if self._piece:
                    self._state = self.PeerState.REQUEST_PASSING
                    # make recursive call to into REQUEST_PASSING block once unchoked
                    return self.evaluate_msg(msg)
            else:
                self.loseConnection(
                    f"msg type of {msg.msg_name} unexpected during: {self._state}"
                )

        elif self._state == self.PeerState.REQUEST_PASSING:
            LOG.info(f"{self.host}, {self.port}: {self._peer_state}")
            if msg.msg_name == "piece":
                finished = self._piece.write_block(**msg.msg_payload_parsed)
                if finished:
                    LOG.info(
                        f"{self.host}, {self.port}: Finished downloading piece {self._piece.index}, getting new piece."
                    )
                    self._piece = None
                    if self._get_piece():
                        return msg.pack_msg("request_all", self._piece)
                    else:
                        self.loseConnection(
                            f"{self.host}, {self.port}: Closing peer connection since there are no more needed pieces."
                        )
                else:
                    return msg.pack_msg("keep-alive")
            elif msg.msg_name == "unchoke":
                self._peer_state["am_choking"] = False
                if (
                    self._peer_state["am_interested"]
                    and not self._peer_state["am_choking"]
                ):
                    LOG.info("{self.host}, {self.port}: Sending request for all blocks")
                    if self._get_piece():
                        return msg.pack_msg("request_all", self._piece)
                    else:
                        self.loseConnection(
                            f"{self.host}, {self.port}: Closing peer connection since there are no more needed pieces."
                        )
            elif msg.msg_name == "choke":
                self._peer_state["am_choking"] = True
                LOG.info("Peer choked, waiting for unchoke to resume requests.")
                return None
            else:
                self.loseConnection(
                    f"msg type of {msg.msg_name} unexpected during: {self._state}"
                )
        else:
            self.loseConnection(
                f"Unexpected case: msg type of {msg.msg_name} during: {self._state}"
            )

    def loseConnection(self, reason):
        """Peer application logic related ``transport.loseConnection``.

        Cleans up Peer connection by returning piece and making
        call to cleanly end TCP connection.
        """
        LOG.info(f"calling loseConnection for {self.host} due to: {reason}")
        LOG.info(
            f"PROGESS: {len(self._writer.curr_pieces())}/{self._piece_manager._md.piece_count}"
        )
        LOG.info(
            f"MISSING: {set(range(self._piece_manager._md.piece_count)) - self._writer.curr_pieces()}"
        )
        if len(self._writer.curr_pieces()) / self._piece_manager._md.piece_count == 1:
            LOG.info(f"PIECE DOWNLOAD FINISHED!")
            try:
                self._reactor.stop()
            except ReactorNotRunning:
                # exception thrown if reactor is already stopped
                pass

        self.transport.loseConnection()
        if self._piece:
            LOG.info(f"loseConnection: returning {self._piece} to queue")
            self._piece_manager.return_piece(self._piece)
            self._piece = None
