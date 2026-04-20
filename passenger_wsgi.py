import sys
import os

BASE_DIR = os.path.dirname(__file__)
sys.path.insert(0, BASE_DIR)

from a2wsgi import ASGIMiddleware
from src.api import app

application = ASGIMiddleware(app)