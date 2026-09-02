# -*- coding: utf-8 -*-
"""وب‌سرور محلی تایل و فایل‌های Leaflet با چرخه عمر یکپارچه."""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

from asset_manager import leaflet_assets_available, VENDOR_DIR as ASSET_VENDOR_DIR

TILE_PATTERN = re.compile(r"^/tile/(\d+)/(\d+)/(\d+)\.png$")
VENDOR_PATTERN = re.compile(r"^/vendor/(leaflet\.js|leaflet\.css|images/[A-Za-z0-9_.-]+)$")
VENDOR_DIR = str(ASSET_VENDOR_DIR)

_SERVER = None
_THREAD = None
_PORT = 8765
_LOCK = threading.RLock()


class TileRequestHandler(BaseHTTPRequestHandler):
    db_path = None
    _thread_local = threading.local()

    def _get_connection(self):
        conn = getattr(self._thread_local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
            self._thread_local.conn = conn
        return conn

    def _send_headers(self, status, content_type=None, length=None, cache_seconds=3600):
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            payload = b"ok"
            self._send_headers(200, "text/plain; charset=utf-8", len(payload), 0)
            self.wfile.write(payload)
            return

        vendor_match = VENDOR_PATTERN.match(path)
        if vendor_match:
            self._serve_vendor_file(vendor_match.group(1))
            return

        match = TILE_PATTERN.match(path)
        if not match:
            self._send_headers(404, "text/plain; charset=utf-8", 0, 0)
            return

        z, x, y = map(int, match.groups())
        row = self._get_connection().execute(
            "SELECT image_data FROM tiles WHERE z=? AND x=? AND y=?", (z, x, y)
        ).fetchone()
        if row and row[0]:
            tile_data = row[0]
            self._send_headers(200, "image/png", len(tile_data), 86400)
            self.wfile.write(tile_data)
        else:
            self._send_headers(204, None, 0, 60)

    def _serve_vendor_file(self, relative_path):
        normalized = os.path.normpath(relative_path).replace("\\", "/")
        if normalized.startswith("../") or normalized.startswith("/"):
            self._send_headers(403, "text/plain", 0, 0)
            return
        file_path = os.path.join(VENDOR_DIR, normalized)
        if not os.path.isfile(file_path):
            self._send_headers(404, "text/plain", 0, 0)
            return
        if normalized.endswith(".js"):
            content_type = "application/javascript; charset=utf-8"
        elif normalized.endswith(".css"):
            content_type = "text/css; charset=utf-8"
        else:
            content_type = "image/png"
        content = open(file_path, "rb").read()
        self._send_headers(200, content_type, len(content), 86400)
        self.wfile.write(content)

    def log_message(self, format, *args):
        pass


class _ThreadingServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_tile_server(db, host="127.0.0.1", preferred_port=8765):
    """سرور را فقط یک بار اجرا می‌کند و در صورت اشغال پورت، پورت آزاد بعدی را می‌یابد."""
    global _SERVER, _THREAD, _PORT
    with _LOCK:
        if _SERVER is not None:
            TileRequestHandler.db_path = db.db_path
            return _SERVER
        TileRequestHandler.db_path = db.db_path
        last_error = None
        for port in range(preferred_port, preferred_port + 11):
            try:
                server = _ThreadingServer((host, port), TileRequestHandler)
                _PORT = port
                _SERVER = server
                _THREAD = threading.Thread(target=server.serve_forever, daemon=True, name="JavanroodTileServer")
                _THREAD.start()
                return server
            except OSError as exc:
                last_error = exc
        raise RuntimeError(f"هیچ پورت آزادی برای سرور نقشه محلی پیدا نشد: {last_error}")


def update_tile_server_database(db):
    TileRequestHandler.db_path = db.db_path


def stop_tile_server():
    global _SERVER, _THREAD
    with _LOCK:
        if _SERVER is not None:
            try:
                _SERVER.shutdown()
                _SERVER.server_close()
            finally:
                _SERVER = None
                _THREAD = None


def get_tile_server_port():
    return _PORT


def get_tile_server_base_url():
    return f"http://127.0.0.1:{_PORT}"


def leaflet_vendor_files_available():
    return leaflet_assets_available()
