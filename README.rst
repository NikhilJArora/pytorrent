=========
pytorrent
=========


.. image:: https://img.shields.io/pypi/v/pytorrent.svg
        :target: https://pypi.python.org/pypi/pytorrent

.. image:: https://img.shields.io/travis/nikhiljarora/pytorrent.svg
        :target: https://travis-ci.com/nikhiljarora/pytorrent

.. image:: https://readthedocs.org/projects/bittorrent-client/badge/?version=latest
        :target: https://bittorrent-client.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status




Bittorrent client written written for learning purposes.


* Free software: MIT license
* Documentation: https://bittorrent-client.readthedocs.io.


Features
--------

* support for http Trackers
* support for download via .torrent files (no Magnet links)
* support for stopping/resuming downloads
* support for both single and multi-file torrents


Get started
-----------

Once installed, we can interact with `PyTorrent` using the following code snippet:

.. code-block:: python

    from pytorrent.client import PyTorrent

    torrent_file = "/path/to/file.torrent"
    pt = PyTorrent(torrent_file)

    pt.start()  # starts the download of torrent pieces

    output_location = "/path/to/output/dir/"  # optional
    pt.create_files(output_location)  # creates final file/files

If prefered, we can also use the CLI instead:

.. code-block:: bash

    $ pytorrent [-o, --output-dir DIRECTORY] "/path/to/file.torrent"

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
