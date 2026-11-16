import os
import sys
import json

# Add the project root to Python path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import app as flask_app


def app(environ, start_response):
    """WSGI wrapper that logs environ for debugging and fixes PATH_INFO."""
    
    # Log key environ vars for debugging
    debug_info = {
        'PATH_INFO': environ.get('PATH_INFO', ''),
        'SCRIPT_NAME': environ.get('SCRIPT_NAME', ''),
        'REQUEST_URI': environ.get('REQUEST_URI', ''),
        'HTTP_X_MATCHED_PATH': environ.get('HTTP_X_MATCHED_PATH', ''),
        'HTTP_X_FORWARDED_HOST': environ.get('HTTP_X_FORWARDED_HOST', ''),
        'HTTP_X_VERCEL_FORWARDED_FOR': environ.get('HTTP_X_VERCEL_FORWARDED_FOR', ''),
        'QUERY_STRING': environ.get('QUERY_STRING', ''),
        'HTTP_HOST': environ.get('HTTP_HOST', ''),
    }
    print(f"[DEBUG ENVIRON] {json.dumps(debug_info)}", flush=True)

    # Fix: Vercel sets SCRIPT_NAME=/api/index and PATH_INFO=/ 
    # OR sets PATH_INFO=/api/index. We need to ensure Flask sees the right path.
    
    path = environ.get('PATH_INFO', '/')
    script = environ.get('SCRIPT_NAME', '')
    
    # Strategy 1: If x-matched-path contains the original path  
    matched = environ.get('HTTP_X_MATCHED_PATH', '')
    if matched:
        environ['PATH_INFO'] = matched.split('?')[0]
        environ['SCRIPT_NAME'] = ''
    # Strategy 2: If PATH_INFO is /api/index, reset to /
    elif path == '/api/index':
        environ['PATH_INFO'] = '/'
        environ['SCRIPT_NAME'] = ''
    # Strategy 3: If SCRIPT_NAME is /api/index, clear it
    elif script == '/api/index':
        environ['SCRIPT_NAME'] = ''
    
    print(f"[DEBUG FIXED] PATH_INFO={environ.get('PATH_INFO')}, SCRIPT_NAME={environ.get('SCRIPT_NAME')}", flush=True)
    
    return flask_app(environ, start_response)
