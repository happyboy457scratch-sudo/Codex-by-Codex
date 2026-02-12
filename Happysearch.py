-"""Codex-Lite: compact coding assistant with CLI and lightweight web UI."""
+"""Happysearch: tiny search engine web app."""
 
 from __future__ import annotations
 
 import argparse
-import importlib
-import importlib.util
 import json
-import os
-import textwrap
+import time
 from dataclasses import dataclass
 from http import HTTPStatus
 from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
 from pathlib import Path
-from typing import List
+from typing import Dict, List
+from urllib.parse import parse_qs, quote, urlencode, urlparse
+from urllib.request import Request, urlopen
 
-SYSTEM_PROMPT = textwrap.dedent(
-    """
-    You are Codex-Lite, a high-signal coding assistant.
-
-    Core behavior:
-    - Prioritize correctness, then clarity, then brevity.
-    - Provide complete code when asked for code.
-    - Explain assumptions and call out uncertainty explicitly.
-    - Include tests/checks and exact commands to validate.
-    - Prefer practical, idiomatic patterns over clever tricks.
-
-    Output format for coding tasks:
-    1) Brief approach summary.
-    2) Implementation (code/steps).
-    3) Verification commands.
-    4) Risks or edge cases.
-    """
-).strip()
-
-WEB_DIR = Path(__file__).resolve().parent / "web"
-TEMPLATE_FILES = {
-    "Mini_codex.py": "Mini_codex.py",
-    "README.md": "README.md",
-    "web/index.html": "index.html",
-}
-
-
-def _get_openai_client() -> object | None:
-    """Return an OpenAI client if SDK + credentials are available."""
-    if not os.getenv("OPENAI_API_KEY"):
-        return None
-    if importlib.util.find_spec("openai") is None:
-        return None
-    openai_module = importlib.import_module("openai")
-    return openai_module.OpenAI()
+WEB_DIR = Path(__file__).resolve().parent
 
 
 @dataclass
-class LiteConfig:
-    model: str = "gpt-4o-mini"
-    temperature: float = 0.1
-    max_tokens: int = 900
-    planning_tokens: int = 280
-    critique_tokens: int = 280
-
-
-class CodexLite:
-    """Small assistant wrapper using a plan -> draft -> critique -> final loop."""
-
-    def __init__(self, config: LiteConfig):
-        self.config = config
-        self.client = _get_openai_client()
-
-    def _responses_create(self, prompt: str, max_tokens: int, temperature: float) -> str:
-        """Call the Responses API with a stable input shape."""
-        response = self.client.responses.create(
-            model=self.config.model,
-            temperature=temperature,
-            max_output_tokens=max_tokens,
-            input=[
-                {
-                    "role": "system",
-                    "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
-                },
-                {
-                    "role": "user",
-                    "content": [{"type": "input_text", "text": prompt}],
-                },
-            ],
+class SearchResult:
+    title: str
+    snippet: str
+    url: str
+
+
+class Happysearch:
+    def __init__(self, timeout_seconds: float = 6.0) -> None:
+        self.timeout_seconds = timeout_seconds
+
+    def _get_json(self, url: str) -> Dict:
+        request = Request(
+            url,
+            headers={
+                "User-Agent": "Happysearch/1.0 (+https://localhost)",
+                "Accept": "application/json",
+            },
         )
-        return response.output_text
-
-    def _chat_completions_create(self, prompt: str, max_tokens: int, temperature: float) -> str:
-        """Fallback path for SDKs that reject Responses payload patterns."""
-        completion = self.client.chat.completions.create(
-            model=self.config.model,
-            temperature=temperature,
-            max_tokens=max_tokens,
-            messages=[
-                {"role": "system", "content": SYSTEM_PROMPT},
-                {"role": "user", "content": prompt},
-            ],
+        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - controlled URL
+            return json.loads(response.read().decode("utf-8"))
+
+    def _wikipedia_results(self, query: str, limit: int = 7) -> List[SearchResult]:
+        params = urlencode(
+            {
+                "action": "query",
+                "list": "search",
+                "srsearch": query,
+                "srlimit": str(limit),
+                "utf8": "",
+                "format": "json",
+            }
         )
-        return completion.choices[0].message.content or ""
-
-    def _model_call(self, prompt: str, max_tokens: int, temperature: float) -> str:
-        """Use Responses first; fallback to Chat Completions for compatibility."""
+        payload = self._get_json(f"https://en.wikipedia.org/w/api.php?{params}")
+
+        items: List[SearchResult] = []
+        for row in payload.get("query", {}).get("search", []):
+            title = row.get("title", "Untitled")
+            snippet = row.get("snippet", "")
+            snippet = snippet.replace("<span class=\"searchmatch\">", "").replace("</span>", "")
+            url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
+            items.append(SearchResult(title=title, snippet=snippet, url=url))
+        return items
+
+    def search(self, query: str) -> Dict:
+        started = time.perf_counter()
         try:
-            return self._responses_create(prompt, max_tokens, temperature)
+            results = self._wikipedia_results(query)
         except Exception:
-            return self._chat_completions_create(prompt, max_tokens, temperature)
-
-    def _offline_answer(self, user_input: str) -> str:
-        return "\n".join(
-            [
-                "Offline mode (no OpenAI SDK and/or OPENAI_API_KEY).",
-                "",
-                "Approach summary:",
-                "- I will still optimize for coding quality by using a strict response scaffold.",
-                "",
-                "Implementation:",
-                f"- Restate request: {user_input}",
-                "- Break work into: requirements -> design -> implementation -> tests.",
-                "- Produce minimal, runnable code and avoid hidden assumptions.",
-                "",
-                "Verification commands:",
-                "- Run formatter/linter for your language (e.g., ruff, black, eslint, gofmt).",
-                "- Run unit tests and a focused smoke test of the changed behavior.",
-                "",
-                "Risks or edge cases:",
-                "- Missing constraints (runtime, framework, API shape) can cause wrong choices.",
-                "- If you share those constraints, I can return a concrete production-ready patch.",
+            results = [
+                SearchResult(
+                    title=f"Search Wikipedia for: {query}",
+                    snippet="Live search source unavailable here, so use this direct Wikipedia query link.",
+                    url=f"https://en.wikipedia.org/w/index.php?search={quote(query)}",
+                ),
+                SearchResult(
+                    title=f"Search DuckDuckGo for: {query}",
+                    snippet="Open web results directly in DuckDuckGo.",
+                    url=f"https://duckduckgo.com/?q={quote(query)}",
+                ),
             ]
-        )
-
-    def answer(self, user_input: str) -> str:
-        if not self.client:
-            return self._offline_answer(user_input)
-
-        try:
-            plan_prompt = (
-                "Create a concise implementation plan for this coding request. "
-                "Include assumptions, test strategy, and likely edge cases.\n\n"
-                f"Request: {user_input}"
-            )
-            plan = self._model_call(plan_prompt, self.config.planning_tokens, self.config.temperature)
 
-            draft_prompt = (
-                f"User request: {user_input}\n\n"
-                f"Implementation plan: {plan}\n\n"
-                "Write the best possible answer for a coding user."
-            )
-            draft = self._model_call(draft_prompt, self.config.max_tokens, self.config.temperature)
+        elapsed_ms = int((time.perf_counter() - started) * 1000)
 
-            critique_prompt = (
-                "Critique the draft answer for correctness, omissions, weak tests, "
-                "and unclear assumptions. Return only actionable improvements.\n\n"
-                f"User request: {user_input}\n\n"
-                f"Draft answer: {draft}"
-            )
-            critique = self._model_call(critique_prompt, self.config.critique_tokens, 0.0)
+        return {
+            "query": query,
+            "engine": "Happysearch",
+            "elapsed_ms": elapsed_ms,
+            "results": [result.__dict__ for result in results],
+        }
 
-            final_prompt = (
-                f"User request: {user_input}\n\n"
-                f"Plan: {plan}\n\n"
-                f"Draft: {draft}\n\n"
-                f"Critique: {critique}\n\n"
-                "Produce the improved final answer, incorporating critique fixes."
-            )
-            return self._model_call(final_prompt, self.config.max_tokens, self.config.temperature)
-        except Exception as exc:
-            return (
-                "I hit an OpenAI API compatibility issue while generating a response.\n"
-                f"Error: {exc}\n\n"
-                "Falling back to offline guidance:\n\n"
-                f"{self._offline_answer(user_input)}"
-            )
 
-class CodexLiteHandler(BaseHTTPRequestHandler):
-    assistant: CodexLite | None = None
+class HappysearchHandler(BaseHTTPRequestHandler):
+    engine = Happysearch()
 
-    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
+    def _send_json(self, payload: Dict, status: int = HTTPStatus.OK) -> None:
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
-        if self.path in {"/", "/index.html"}:
-            self._serve_file("index.html")
-            return
-        if self.path.startswith("/assets/"):
-            self._serve_file(self.path.lstrip("/"))
-            return
-        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
-
-    def do_POST(self) -> None:
-        if self.path != "/api/ask":
-            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
-            return
+        parsed = urlparse(self.path)
 
-        if not self.assistant:
-            self._send_json({"error": "assistant not configured"}, HTTPStatus.INTERNAL_SERVER_ERROR)
+        if parsed.path in {"/", "/index.html"}:
+            self._serve_file("index.html")
             return
 
-        length = int(self.headers.get("Content-Length", "0"))
-        raw_body = self.rfile.read(length)
-        try:
-            payload = json.loads(raw_body.decode("utf-8"))
-        except json.JSONDecodeError:
-            self._send_json({"error": "invalid JSON body"}, HTTPStatus.BAD_REQUEST)
-            return
+        if parsed.path == "/api/search":
+            raw_query = parse_qs(parsed.query).get("q", [""])[0]
+            query = raw_query.strip()
+            if not query:
+                self._send_json({"error": "Query parameter 'q' is required."}, HTTPStatus.BAD_REQUEST)
+                return
 
-        prompt = str(payload.get("prompt", "")).strip()
-        if not prompt:
-            self._send_json({"error": "prompt is required"}, HTTPStatus.BAD_REQUEST)
+            payload = self.engine.search(query)
+            self._send_json(payload)
             return
 
-        answer = self.assistant.answer(prompt)
-        self._send_json({"answer": answer})
+        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
 
 
 def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
-    parser = argparse.ArgumentParser(description="Run Codex-Lite.")
-    parser.add_argument("prompt", nargs="?", help="User prompt to answer")
-    parser.add_argument("--model", default="gpt-4o-mini", help="Model name")
-    parser.add_argument("--temperature", type=float, default=0.1)
-    parser.add_argument("--max-tokens", type=int, default=900)
-    parser.add_argument("--planning-tokens", type=int, default=280)
-    parser.add_argument("--critique-tokens", type=int, default=280)
-    parser.add_argument("--serve", action="store_true", help="Run web UI server")
+    parser = argparse.ArgumentParser(description="Run the Happysearch web server.")
     parser.add_argument("--host", default="127.0.0.1", help="Web server host")
     parser.add_argument("--port", type=int, default=8000, help="Web server port")
-    parser.add_argument(
-        "--create-yourself",
-        metavar="TARGET_DIR",
-        help="Scaffold a standalone Codex-Lite copy into TARGET_DIR",
-    )
     return parser.parse_args(argv)
 
 
-def create_yourself(target_dir: str) -> Path:
-    """Scaffold a standalone Codex-Lite copy in target_dir."""
-    destination = Path(target_dir).expanduser().resolve()
-    destination.mkdir(parents=True, exist_ok=True)
-
-    project_root = Path(__file__).resolve().parent
-    for relative_dest, source_name in TEMPLATE_FILES.items():
-        source = project_root / source_name
-        target = destination / relative_dest
-        target.parent.mkdir(parents=True, exist_ok=True)
-        target.write_bytes(source.read_bytes())
-
-    return destination
-
-
-def run_server(assistant: CodexLite, host: str, port: int) -> None:
-    if not WEB_DIR.exists():
-        raise FileNotFoundError(f"Web UI directory not found: {WEB_DIR}")
-
-    CodexLiteHandler.assistant = assistant
-    server = ThreadingHTTPServer((host, port), CodexLiteHandler)
-    print(f"Codex-Lite web UI running at http://{host}:{port}")
-    server.serve_forever()
-
-
 def main() -> None:
     args = parse_args()
-
-    if args.create_yourself:
-        destination = create_yourself(args.create_yourself)
-        print(f"Created Codex-Lite scaffold at: {destination}")
-        return
-
-    assistant = CodexLite(
-        LiteConfig(
-            model=args.model,
-            temperature=args.temperature,
-            max_tokens=args.max_tokens,
-            planning_tokens=args.planning_tokens,
-            critique_tokens=args.critique_tokens,
-        )
-    )
-
-    if args.serve:
-        run_server(assistant, args.host, args.port)
-        return
-
-    if not args.prompt:
-        raise SystemExit("Provide a prompt or use --serve to launch the web UI.")
-
-    print(assistant.answer(args.prompt))
+    server = ThreadingHTTPServer((args.host, args.port), HappysearchHandler)
+    print(f"Happysearch running at http://{args.host}:{args.port}")
+    server.serve_forever()
 
 
 if __name__ == "__main__":
     main()
