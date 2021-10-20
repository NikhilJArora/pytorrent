=====
Usage
=====

To use bittorrent client in a project::

    from pytorrent.client import PyTorrent
    
    # TORRENT_PATH = "my/path/to/file.torrent"
    pt = PyTorrent(TORRENT_PATH)
    pt.start()    
