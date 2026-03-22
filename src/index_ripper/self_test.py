from __future__ import annotations

import contextlib
import html.parser
import http.server
import os
import socket
import tempfile
import threading
from dataclasses import dataclass

import urllib.parse
import urllib.request

@dataclass(frozen=True)
class SelfTestResult:
    total: int
    files: int
    directories: int


def _write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        file_obj.write(content)


def _find_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _LocalHTTPServer:
    def __init__(self, directory: str):
        self._directory = directory
        self._server = None
        self._thread = None
        self.port = None

    def __enter__(self):
        port = _find_free_port()

        class _QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                return

        def handler_factory(*args, **kwargs):
            return _QuietHandler(*args, directory=self._directory, **kwargs)

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler_factory)
        self.port = port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        return False


class _DummyUI:
    def log_message(self, message: str) -> None:
        _ = message


class _HrefParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag != "a":
            return
        for k, v in attrs:
            if k == "href" and isinstance(v, str) and v:
                self.hrefs.append(v)
                return


def _fetch_html(url: str, timeout: float = 2.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "IndexRipperSelfTest/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def _same_origin(a: str, b: str) -> bool:
    pa = urllib.parse.urlparse(a)
    pb = urllib.parse.urlparse(b)
    return pa.scheme == pb.scheme and pa.netloc == pb.netloc


def _crawl(base_url: str) -> tuple[set[str], set[str]]:
    seen_pages: set[str] = set()
    files: set[str] = set()
    dirs: set[str] = set()

    def visit(page_url: str) -> None:
        if page_url in seen_pages:
            return
        seen_pages.add(page_url)

        html = _fetch_html(page_url)
        parser = _HrefParser()
        parser.feed(html)

        for href in parser.hrefs:
            if not href or href in (".", "..", "/"):
                continue
            if href.startswith("?"):
                continue

            full = urllib.parse.urljoin(page_url, href)
            if not _same_origin(base_url, full):
                continue

            if href.endswith("/") or full.endswith("/"):
                if not full.endswith("/"):
                    full += "/"
                if full not in dirs:
                    dirs.add(full)
                    visit(full)
            else:
                files.add(full)

    visit(base_url)
    return files, dirs


def run_self_test() -> SelfTestResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = tmpdir
        sub = os.path.join(tmpdir, "sub")
        os.makedirs(sub, exist_ok=True)

        _write_text(
            os.path.join(root, "index.html"),
            """<!doctype html>
<html>
  <body>
    <a href=\"sub/\">sub/</a>
    <a href=\"a.txt\">a.txt</a>
    <a href=\"space%20name.txt\">space name.txt</a>
  </body>
</html>
""",
        )
        _write_text(os.path.join(root, "a.txt"), "hello\n")
        _write_text(os.path.join(root, "space name.txt"), "hello\n")

        _write_text(
            os.path.join(sub, "index.html"),
            """<!doctype html>
<html>
  <body>
    <a href=\"b.bin\">b.bin</a>
  </body>
</html>
""",
        )
        with open(os.path.join(sub, "b.bin"), "wb") as file_obj:
            file_obj.write(b"\x00\x01\x02")

        with _LocalHTTPServer(directory=tmpdir) as server:
            url = f"http://127.0.0.1:{server.port}/"
            files, dirs = _crawl(url)

        return SelfTestResult(total=len(files) + len(dirs), files=len(files), directories=len(dirs))
