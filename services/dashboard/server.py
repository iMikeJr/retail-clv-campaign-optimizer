"""Serve only local assets; inject the configured host API port without a build."""
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path

API_PORT=int(os.environ.get('API_PORT','8000'))

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/config.js':
            body=('window.CAMPAIGN_CONFIG = '+json.dumps({'apiPort':API_PORT})+';').encode()
            self.send_response(200)
            self.send_header('Content-Type','application/javascript')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

if __name__=='__main__':
    os.chdir(Path(__file__).parent)
    ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
