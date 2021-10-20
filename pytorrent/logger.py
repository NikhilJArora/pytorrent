"""Logging setup.
"""
import logging
import sys

# logger formating
BRIEF_FORMAT = "%(levelname)s %(asctime)s - %(name)s: %(message)s"
VERBOSE_FORMAT = (
    "%(levelname)s|%(asctime)s|%(name)s|%(filename)s|"
    "%(funcName)s|%(lineno)d: %(message)s"
)
FORMAT_TO_USE = VERBOSE_FORMAT


def get_logger(name=None, log_level=logging.INFO):
    """Sets the basic logging features for the application
    Parameters
    ----------
    name : str, optional
        The name of the logger. Defaults to ``None``
    log_level : int, optional
        The logging level. Defaults to ``logging.INFO``
    Returns
    -------
    logging.Logger
        Returns a Logger obejct which is set with the passed in paramters.
        Please see the following for more details:
        https://docs.python.org/2/library/logging.html
    """
    logging.basicConfig(format=FORMAT_TO_USE, stream=sys.stdout, level=log_level)
    logger = logging.getLogger(name)
    return logger
