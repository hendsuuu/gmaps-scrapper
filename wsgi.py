"""
WSGI entrypoint for running the Flask app behind Passenger/cPanel.
"""

from __future__ import annotations

import logging
import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Configure a file logger so errors end up in stderr.log on cPanel
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    stream=sys.stderr,
)

try:
    from src.api import app
    application = app
except Exception:
    # If the Flask app fails to import, log the traceback and return a
    # minimal WSGI app that shows the error (visible in stderr.log).
    traceback.print_exc(file=sys.stderr)
    sys.stderr.flush()

    def application(environ, start_response):
        status = "500 Internal Server Error"
        body = b"Application failed to start. Check stderr.log for details."
        start_response(status, [
            ("Content-Type", "text/plain"),
            ("Content-Length", str(len(body))),
        ])
        return [body]
