#!/usr/bin/env python3
"""Serve _dist/ locally for preview. Usage: python3 _theme/serve.py [port]"""
import http.server
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_dist')

os.chdir(DIST)


class CleanURLHandler(http.server.SimpleHTTPRequestHandler):
    """Serves index.html for clean URLs (e.g. /about-us -> /about-us/index.html)."""

    def do_GET(self):
        # Strip query string for file lookup
        path = self.path.split('?')[0].split('#')[0]

        # If path doesn't have an extension and doesn't end with /,
        # try serving path/index.html
        if '.' not in os.path.basename(path) and not path.endswith('/'):
            index_path = os.path.join(DIST, path.lstrip('/'), 'index.html')
            if os.path.isfile(index_path):
                self.path = path.rstrip('/') + '/index.html'
        elif path.endswith('/'):
            index_path = os.path.join(DIST, path.lstrip('/'), 'index.html')
            if os.path.isfile(index_path):
                self.path = path + 'index.html'

        return super().do_GET()


with http.server.HTTPServer(('', PORT), CleanURLHandler) as httpd:
    print(f'Serving {DIST} on http://localhost:{PORT}')
    httpd.serve_forever()
