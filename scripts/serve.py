#!/usr/bin/env python3
"""SPA fallback HTTP server on :8000 — 所有 404 返回 index.html
由 supervisor 托管，沙箱重启后自动恢复。
额外提供 /api/memo 接口：云端备份备忘录（GET 取 / POST 存），供手机 PWA 调用。"""
import http.server
import os
import socketserver
import json
import datetime

WORKSPACE = "/workspace"
INDEX = os.path.join(WORKSPACE, "index.html")
PORT = 8000
MEMO_FILE = os.path.join(WORKSPACE, "data", "memo.json")

# 允许跨域的来源（GitHub Pages 与隧道域名）
ALLOW_ORIGINS = "*"


def now_iso():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def load_memo():
    try:
        with open(MEMO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"text": "", "updated": None}


def save_memo(text):
    data = {"text": text, "updated": now_iso()}
    os.makedirs(os.path.dirname(MEMO_FILE), exist_ok=True)
    with open(MEMO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


class FallbackHandler(http.server.SimpleHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", ALLOW_ORIGINS)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].split("#")[0]

        # 备忘录云端读取接口
        if path == "/api/memo":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps(load_memo(), ensure_ascii=False).encode("utf-8"))
            return

        abs_path = os.path.normpath(os.path.join(WORKSPACE, path.lstrip("/")))
        if not abs_path.startswith(WORKSPACE):
            self.send_error(403)
            return
        if os.path.isfile(abs_path):
            super().do_GET()
        else:
            self.serve_index()

    def do_POST(self):
        path = self.path.split("?")[0].split("#")[0]
        if path == "/api/memo":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b"{}"
                payload = json.loads(body.decode("utf-8"))
                text = payload.get("text", "")
                data = save_memo(text)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._cors()
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self._cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return
        self.send_error(404)

    def serve_index(self):
        try:
            with open(INDEX, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self._cors()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))

    def log_message(self, fmt, *args):
        print(f"[8000] {fmt % args}")


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    srv = ReusableTCPServer(("0.0.0.0", PORT), FallbackHandler)
    print(f"SPA fallback + memo API serving {WORKSPACE} on :{PORT}")
    srv.serve_forever()
