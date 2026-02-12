#!/usr/bin/env python3
"""Happysearch: tiny search engine web app."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen

WEB_DIR = Path(__file__).resolve().parent


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str


class Happysearch:
    def __init__(self, timeout_seconds: float = 6.0) -> None:
        self.timeout_seconds = timeout_seconds

    def _get_json(self, url: str) -> Dict:
        request = Request(
            url,
            headers={
                "User-Agent": "Happysearch/1.0 (+https://localhost)",
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - controlled URL
            return json.loads(response.read().decode("utf-8"))

    def _wikipedia_results(self, query: str, limit: int = 7) -> List[SearchResult]:
        params = urlencode(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": str(limit),
                "utf8": "",
                "format": "json",
            }
        )
        payload = self._get_json(f"https://en.wikipedia.org/w/api.php?{params}")

        items: List[SearchResult] = []
        for row in payload.get("query", {}).get("search", []):
            title = row.get("title", "Untitled")
            snippet = row.get("snippet", "")
            snippet = snippet.replace("<span class=\"searchmatch\">", "").replace("</span>", "")
            url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
            items.append(SearchResult(title=title, snippet=snippet, url=url))
        return items

    def search(self, query: str) -> Dict:
        started = time.perf_counter()
        try:
            results = self._wikipedia_results(query)
        except Exception:
            results = [
                SearchResult(
                    title=f"Search Wikipedia for: {query}",
                    snippet="Live search source unavailable here, so use this direct Wikipedia query link.",
                    url=f"https://en.wikipedia.org/w/index.php?search={quote(query)}",
                ),
                SearchResult(
                    title=f"Search DuckDuckGo for: {query}",
                    snippet="Open web results directly in DuckDuckGo.",
                    url=f"https://duckduckgo.com/?q={quote(query)}",
                ),
            ]

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        return {
            "query": query,
            "engine": "Happysearch",
            "elapsed_ms": elapsed_ms,
            "results": [result.__dict__ for result in results],
        }


class HappysearchHandler(BaseHTTPRequestHandler):
    engine = Happysearch()

    def _send_json(self, payload: Dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, relative_path: str) -> None:
        safe_path = (WEB_DIR / relative_path).resolve()
        if WEB_DIR not in safe_path.parents and safe_path != WEB_DIR:
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
            return
        if not safe_path.exists() or safe_path.is_dir():
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        content_type = "text/plain; charset=utf-8"
        if safe_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif safe_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif safe_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"

        body = safe_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path in {"/", "/index.html"}:
            self._serve_file("index.html")
            return

        if parsed.path == "/api/search":
            raw_query = parse_qs(parsed.query).get("q", [""])[0]
            query = raw_query.strip()
            if not query:
                self._send_json({"error": "Query parameter 'q' is required."}, HTTPStatus.BAD_REQUEST)
                return

            payload = self.engine.search(query)
            self._send_json(payload)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Happysearch web server.")
    parser.add_argument("--host", default="127.0.0.1", help="Web server host")
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), HappysearchHandler)
    print(f"Happysearch running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
