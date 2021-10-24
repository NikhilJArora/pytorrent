=========
pytorrent
=========


.. image:: https://img.shields.io/travis/nikhiljarora/pytorrent.svg
        :target: https://travis-ci.com/nikhiljarora/pytorrent

.. image:: https://readthedocs.org/projects/bittorrent-client/badge/?version=latest
        :target: https://bittorrent-client.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status




Simple Bittorrent client written using Python and `Twisted <https://pypi.org/project/Twisted/>`_.


* Free software: MIT license
* Documentation: https://bittorrent-client.readthedocs.io.


Features
--------

* support for http Trackers
* support for download via ``.torrent`` files (no Magnet links)
* support for stopping/resuming downloads
* support for both single and multi-file torrents


Get started
-----------
First lets get our python package installed. I prefer to user conda to create my virtual environments but any should work.

With `conda <https://docs.conda.io/en/latest/miniconda.html>`_ installed lets create a virtual environment (venv or virtualenv would also work):

.. code-block:: bash

    conda create -n pytorrent python=3.8 -y
    conda activate pytorrent
    
Now with our venv activated lets clone down the repo and install it:

.. code-block:: bash

    git clone https://github.com/NikhilJArora/pytorrent.git
    cd pytorrent
    pip install -e .


Once installed, we interact with the ``pytorrent`` CLI as follows:

.. code-block:: bash

    $ pytorrent [-o, --output-dir DIRECTORY] "/path/to/file.torrent"

If prefered, we can interact directly with the main `PyTorrent` class to achieve the same result with the Python REPL:

.. code-block:: python

    from pytorrent.client import PyTorrent

    torrent_file = "/path/to/file.torrent"
    pt = PyTorrent(torrent_file)

    pt.start()  # starts the download of torrent pieces

    output_location = "/path/to/output/dir/"  # optional
    pt.create_files(output_location)  # creates final file/files

There are also some other classes work noting that expose other useful functionality:

* to interact directly with the Torrent metadata class: ``pytorrent.torrent_file.TorrentMD``
* to interact directly with the Torrent Tracker class: ``pytorrent.connections.Tracker``


Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
