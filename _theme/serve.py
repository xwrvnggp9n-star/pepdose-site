#!/usr/bin/env python3
"""Serve _dist/ locally for preview. Usage: python3 _theme/serve.py [port]"""
import http.server
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_dist')

os.chdir(DIST)
handler = http.server.SimpleHTTPRequestHandler
with http.server.HTTPServer(('', PORT), handler) as httpd:
    print(f'Serving {DIST} on http://localhost:{PORT}')
    httpd.serve_forever()
