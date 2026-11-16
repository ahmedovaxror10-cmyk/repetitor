import os
import sys
from urllib.parse import unquote

# Add the project root to Python path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app as flask_app


class VercelWSGIMiddleware:
    """
    Ensures Flask receives the correct PATH_INFO and SCRIPT_NAME on Vercel.
    Vercel rewrites incoming URLs to /api/index, but stores the original
    requested path in HTTP_X_MATCHED_PATH (e.g. /kirish, /qidiruv, /admin).
    """

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        matched = environ.get("HTTP_X_MATCHED_PATH") or ""
        if matched:
            path, _, query = matched.partition("?")
            environ["PATH_INFO"] = unquote(path)
            if query and not environ.get("QUERY_STRING"):
                environ["QUERY_STRING"] = query
        else:
            path = environ.get("PATH_INFO", "/")
            if path.startswith("/api/index"):
                environ["PATH_INFO"] = path[len("/api/index"):] or "/"

        environ["SCRIPT_NAME"] = ""
        return self.wsgi_app(environ, start_response)


# Vercel looks for the WSGI/ASGI entrypoint named `app`
app = VercelWSGIMiddleware(flask_app)
