""" Init file. """
from importlib.metadata import PackageNotFoundError, version

from .core import *
from .exec_notebook import exec_notebook, run_notebook
from .pylint_notebook import pylint_notebook

try:
    __version__ = version("py-nbtools")
except PackageNotFoundError:
    __version__ = "0.0.0"  # e.g., running from a source tree
