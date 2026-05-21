import logging

import click
from rich.logging import RichHandler

from neolab.server import run


def _setup_logging(level: str) -> None:
    """spdlog-style colored output via Rich.

    Format::

        [22:52:47.118] INFO     [neolab.server] message goes here
    """
    handler = RichHandler(
        show_time=True,
        show_level=True,
        show_path=False,
        rich_tracebacks=True,
        markup=False,
        omit_repeated_times=False,
        log_time_format=lambda dt: dt.strftime("[%H:%M:%S.%f]")[:-4] + "]",
    )
    logging.basicConfig(
        level=level.upper(),
        format="[%(name)s] %(message)s",
        handlers=[handler],
        force=True,
    )
    # aiohttp logs every request at INFO; keep it visible but not louder than that.
    logging.getLogger("aiohttp.access").setLevel(logging.INFO)


@click.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind.")
@click.option("--port", default=9494, type=int, show_default=True, help="TCP port to listen on.")
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    show_default=True,
)
def main(host: str, port: int, log_level: str) -> None:
    """Run the neolab server."""
    _setup_logging(log_level)
    run(host=host, port=port)
