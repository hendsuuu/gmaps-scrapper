"""
Passenger entrypoint.

Keep this file minimal so Passenger never ends up importing itself recursively.
"""

from wsgi import application
