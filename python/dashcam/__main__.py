"""
Package entrypoint for `python -m dashcam`.

This module forwards execution to the top-level `dashcam.py` script
so the package can be executed as a module when run under systemd
or with `python -m dashcam`.
"""
from runpy import run_path
import os

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dashcam.py'))

if __name__ == '__main__':
    run_path(SCRIPT_PATH, run_name='__main__')
