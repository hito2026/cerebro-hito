#!/usr/bin/env python3
"""Endpoint local mínimo para que Cerebro dispare una publicación sanitizada."""
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(json.dumps({"client":self.client_address[0],"request":fmt % args}),flush=True)

    def reply(self,status,payload):
        body=json.dumps(payload,ensure_ascii=False).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)

    def do_GET(self):
        self.reply(200,{"ok":True,"service":"cerebro-dashboard-publisher","mode":"sanitized"}) if self.path=="/health" else self.reply(404,{"ok":False,"error":"not found"})

    def do_POST(self):
        if self.path!="/v1/publish":self.reply(404,{"ok":False,"error":"not found"});return
        try:
            run=subprocess.run(["/usr/bin/python3",str(ROOT/"scripts/update_dashboard.py"),"--publish"],cwd=ROOT,capture_output=True,text=True,timeout=180)
            if run.returncode:self.reply(502,{"ok":False,"error":"update failed","detail":run.stderr[-500:]});return
            self.reply(200,json.loads(run.stdout.strip().splitlines()[-1]))
        except Exception as exc:
            self.reply(500,{"ok":False,"error":type(exc).__name__})


ThreadingHTTPServer(("127.0.0.1",18766),Handler).serve_forever()
