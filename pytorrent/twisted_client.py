"""Twisted client code holding Protocol & ClientFactory."""

from sys import stdout

from twisted.internet.protocol import ClientFactory, Protocol

from pytorrent.connections import Peer

from .logger import get_logger

LOG = get_logger(__name__)


class PeerProtocal(Protocol):
    """Peer Protocal logic.

    Peer protocal that will offload calls to ``Peer`` instance.
    """

    def __init__(self, peer: Peer) -> None:
        self._peer = peer
        super().__init__()

    def connectionMade(self):
        """Called when TCP connection is successfully made."""
        LOG.debug("connectionMade event triggered")
        # allows peer to directly write to the transport
        self._peer.transport = self.transport
        self._peer.send_handshake()

    def dataReceived(self, data):
        LOG.debug("PeerProtocol `dataReceived` event.")
        self._peer.dataReceived(data)

    def connectionLost(self, reason):
        """Peer connection lost."""
        LOG.debug(f"connectionLost event: Peer connection lost. Reason: {reason}")

        self._peer.loseConnection(
            reason
        )  # cleans up peer gracefully (return unfinished piece to queue)


class PeerClientFactory(ClientFactory):
    PeerCounter = 0

    def __init__(self, peer: Peer) -> None:
        self._peer: Peer = peer
        super().__init__()

    def buildProtocol(self, addr):
        return PeerProtocal(self._peer)

    def startedConnecting(self, connector):
        PeerClientFactory.PeerCounter += 1
        LOG.info(
            f"{self._peer.host}: Connected. Current peer count {PeerClientFactory.PeerCounter}."
        )
        LOG.debug(f"PeerClientFactory.PeerCounter: {PeerClientFactory.PeerCounter}")

    def clientConnectionLost(self, connector, reason):
        PeerClientFactory.PeerCounter -= 1
        LOG.info(
            f"{self._peer.host}: Disconnected. Current peer count {PeerClientFactory.PeerCounter}."
        )
        LOG.debug(f"Lost connection to {self._peer.host}.  Reason: {reason}")

    def clientConnectionFailed(self, connector, reason):
        PeerClientFactory.PeerCounter -= 1
        LOG.info(
            f"{self._peer.host}: Connection failed. Current peer count {PeerClientFactory.PeerCounter}."
        )
        LOG.debug(
            f"Connection failed. Reason: {reason}. Current peer count {PeerClientFactory.PeerCounter}."
        )
