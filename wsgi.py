"""
WSGI entrypoint for running the Flask app behind Passenger/cPanel.
"""

from __future__ import annotations

import os
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


from src.api import app


application = app
