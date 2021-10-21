"""Console script for pytorrent."""
import sys

import click

from .client import PyTorrent


@click.command()
@click.argument("torrent", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option(
    "-o",
    "--output-dir",
    "output_location",
    default=None,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
def run(torrent, output_location):
    """Console script for pytorrent.cli.run."""
    click.echo("Replace this message by putting your code into " "pytorrent.cli.run")
    pt = PyTorrent(torrent)
    pt.start()
    pt.create_files(output_location)
    return 0


if __name__ == "__main__":
    sys.exit(run())  # pragma: no cover
