"""Module to hold all buttorrent message handling logic."""
import bitstring

from .logger import get_logger

LOG = get_logger(__name__)


class MsgHandler:
    """Message handler used to parse, pack and unpack msgs.

    Consumer should create single instance per msg payload to be parsed.
    Also exposes helper methods that will allow for msg packing and unpacking.

    Parameters
    ----------
    data : bytes
        raw bytes of msg to be parsed into <length prefix><message ID><payload>
    """

    msg_id_to_name = {
        0: "choke",
        1: "unchoke",
        2: "interested",
        3: "not interested",
        4: "have",
        5: "bitfield",
        6: "request",
        7: "piece",
        8: "cancel",
        9: "port",
    }

    msg_unpackers = {
        "choke": None,
        "unchoke": None,
        "interested": "msg_interested_unpack",
        "not interested": "msg_not_interested_unpack",
        "have": "msg_have_unpack",
        "bitfield": "msg_bitfield_unpack",
        "request": "msg_request_unpack",
        "piece": "msg_piece_unpack",
        "cancel": "msg_cancel_unpack",
        "port": "msg_port_unpack",
    }

    msg_packers = {
        "keep-alive": "msg_keep_alive_pack",
        "choke": "msg_choke_pack",
        "unchoke": "msg_unchoke_pack",
        "interested": "msg_interested_pack",
        "not interested": "msg_not_interested_pack",
        "have": "msg_have_pack",
        "bitfield": "msg_bitfield_pack",
        "request": "msg_request_pack",
        "request_all": "msg_request_all_pack",
        "piece": "msg_piece_pack",
        "cancel": "msg_cancel_pack",
        "port": "msg_port_pack",
    }

    def __init__(self, data: bytes):
        assert data is not None

        self.raw_data = data
        self.is_incomplete = False
        self._set_length_prefix()
        self._validate_payload_length()

    def _set_length_prefix(self):
        """Set the length prefix of msg that is the first 4 bytes.



        Side effect
        -----------
        length_prefix : int
            length prefix of current msg
        """
        length_prefix = bitstring.Bits(self.raw_data[0:4]).int
        if not isinstance(length_prefix, int):
            raise ValueError(
                f"Got invalid length_prefix for following data bytes: {self.raw_data}"
            )
        else:
            self.length_prefix = int(length_prefix)

    def _validate_payload_length(self):
        """Check the length of the payload and ensure we have what is needed.

        Side effect
        -----------
        is_incomplete : bool
            incase msg data is incomplete, set to true so Peer knows to wait for more data.
        """
        if self.length_prefix is None:
            raise AttributeError("Must set prior to validating payload length")

        if len(self.raw_data) < self.length_prefix + 4:
            LOG.debug(
                f"Incomplete msg payload, waiting for entire msg prior to parsing: {len(self.raw_data) - 4} when expected {self.length_prefix}"
            )
            self.is_incomplete = True

    @property
    def msg_id(self):
        """returns msg_id

        Returns
        -------
        int
            msg_id value

        """
        if self.length_prefix == 0:
            return None
        else:
            return self.raw_data[4]

    @property
    def msg_name(self):
        """returns msg_id name

        Returns
        -------
        str
            msg_id name
        """
        if self.length_prefix == 0:
            return None
        else:
            return self.msg_id_to_name[self.raw_data[4]]

    @property
    def msg_payload_raw(self):
        """Returns just the payload bytes."""
        # Single byte length would only contain info for the actual byte
        if self.length_prefix > 1:
            assert (
                len(self.raw_data[5 : self.length_prefix + 4]) == self.length_prefix - 1
            ), (len(self.raw_data[5 : self.length_prefix + 4]), self.length_prefix - 1)
            return self.raw_data[5 : self.length_prefix + 4]
        else:
            return None

    @property
    def msg_payload_parsed(self):
        """Returns payload parsed into dict based on expected keys from msg spec."""
        if not self.msg_payload_raw:
            return None
        else:
            return eval(self.msg_unpackers[self.msg_name])(self.msg_payload_raw)

    @property
    def next_msg_raw_data(self):
        """If data sent to handler is more than single msg, pass off to next call."""
        if len(self.raw_data) > self.length_prefix + 4:
            return self.raw_data[self.length_prefix + 4 :]
        else:
            return None

    def pack_msg(self, name: str, *args, **kwargs):
        """ """
        if name not in self.msg_packers:
            raise KeyError(
                f"{name} not found in potenial msg types: {self.msg_packers.keys()}"
            )
        else:
            return eval(self.msg_packers[name])(*args, **kwargs)


import struct


# msg payload helper functions
def msg_interested_pack():
    return struct.pack(">L", 1) + bytes([2])


def msg_not_interested_pack():
    return struct.pack(">L", 1) + bytes([3])


def msg_keep_alive_pack():
    return struct.pack(">L", 0)


def msg_have_unpack(data):
    """have: <len=0005><id=4><piece index>

    Returns
    -------
    dict with "piece_index"
        when "piece_index" is type int
    """
    assert len(data) == 4
    return {"piece_index": int(bitstring.Bits(data).int)}


def msg_bitfield_unpack(data):
    """<len=0001+X><id=5><bitfield>"""
    return {"bitfield": list(bitstring.BitArray(data))}


def msg_request_unpack(data):
    """<len=0013><id=6><index><begin><length>
    test case:
    b'\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00@\x00'
    0, 32768, 16384

    """
    assert len(data) == 12
    return {
        "index": struct.unpack(">L", data[0:4]),
        "begin": struct.unpack(">L", data[4:8]),
        "length": struct.unpack(">L", data[8:12]),
    }


def msg_request_pack(index, begin, length):
    """<len=0013><id=6><index><begin><length>
    b'\x00\x00\x00\r\x06\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00@\x00'
    0, 32768, 16384 (5 byte prefix_len + msg_id prepended - not sure if it should be handled here)
    """
    return (
        bytes([0, 0, 0, 13, 6])
        + struct.pack(">L", index)
        + struct.pack(">L", begin)
        + struct.pack(">L", length)
    )


def msg_request_all_pack(piece):
    """Forms payload for entire piece using msg_request_pack"""
    payload_ls = []
    for block in piece.blocks:
        payload_ls.append(msg_request_pack(piece.index, block[0], block[1]))

    return b"".join(payload_ls)


def msg_piece_unpack(data):
    """<len=0009+X><id=7><index><begin><block>

    Note: block is subset of piece.
    """
    return {
        "index": struct.unpack(">L", data[0:4])[0],
        "begin": struct.unpack(">L", data[4:8])[0],
        "block": data[8:],
    }


def msg_cancel_pack():
    """out of scope for now"""
    pass


def msg_port_unpack(data):
    """out of scope for now, need to read about this later!"""
    return {"listen-port": struct.unpack(">H", data)[0]}
