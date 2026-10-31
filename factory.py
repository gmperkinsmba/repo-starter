#!/usr/bin/env python3
"""Create and verify small, reviewable repository starters."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import secrets
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SANDBOX = Path.home() / ".secure-repo-factory" / "generated"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_BODY = 8192
FILES = {
    "README.md": "# {name}\n\n> First principle: Keep project setup reviewable and safe to repeat.\n\nA small starter repository with inspectable defaults.\n\n## Start\n\nReview this file and `CONTEXT.md`, then add your project code.\n\n## Data\n\nNo data store is created. Keep real data outside this repository unless you add and review a specific storage plan.\n",
    "CONTEXT.md": "# Project context\n\n- Purpose: Record the project's domain and invariants.\n- Data: No database or user data is included.\n- Changes: Review generated files before use.\n",
    "LICENSE": "MIT License\n\nCopyright (c) {year} The project owner\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the \"Software\"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.\n",
    ".gitignore": "# Local runtime and secrets\n.env\n.env.*\n!.env.example\n*.pem\n*.key\nsecrets/\n.runtime/\n*.db\n*.sqlite\n*.sqlite3\nuploads/\nexports/\n.venv/\nvenv/\n__pycache__/\nbuild/\ndist/\ngraphify-out/\n",
}
SECRET_RE = re.compile(r"(?i)(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+]{16,})")


def safe_slug(value: str) -> str:
    if not isinstance(value, str) or not SLUG_RE.fullmatch(value) or len(value) > 48:
        raise ValueError("Use a lowercase slug with letters, numbers, and single hyphens.")
    return value


def manifest_for(slug: str) -> dict:
    slug = safe_slug(slug)
    content = {name: body.format(name=slug, year="2026") for name, body in FILES.items()}
    return {"schema": 1, "slug": slug, "files": {name: hashlib.sha256(body.encode()).hexdigest() for name, body in content.items()}}


def templates_for(slug: str) -> dict:
    safe_slug(slug)
    return {name: body.format(name=slug, year="2026") for name, body in FILES.items()}


def create_zip(slug: str) -> bytes:
    slug = safe_slug(slug)
    manifest = manifest_for(slug)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, body in FILES.items():
            zf.writestr(f"{slug}/{name}", body.format(name=slug, year="2026"))
        zf.writestr(f"{slug}/.factory-manifest.json", json.dumps(manifest, indent=2) + "\n")
    return out.getvalue()


def generate(slug: str, destination: str, dry_run: bool = False) -> dict:
    slug = safe_slug(slug)
    base = Path(destination).expanduser().resolve()
    target = base / slug
    if base not in target.parents:
        raise ValueError("Destination must be a parent folder.")
    manifest = manifest_for(slug)
    if dry_run:
        return {"target": str(target), "files": manifest["files"], "mode": "dry-run"}
    if target.exists() and (target.is_symlink() or not target.is_dir()):
        raise ValueError("Target must be a normal directory, not a link or file.")
    target.mkdir(parents=True, exist_ok=True)
    manifest_path = target / ".factory-manifest.json"
    old = {}
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            old = {}
    actions = {}
    for name, body in FILES.items():
        path = target / name
        digest = manifest["files"][name]
        if path.is_symlink():
            actions[name] = "symbolic-link; preserved"
            continue
        if path.exists():
            current = hashlib.sha256(path.read_bytes()).hexdigest()
            if current == digest:
                actions[name] = "unchanged"
            elif old.get("files", {}).get(name) == current:
                actions[name] = "edited-generated-file; preserved"
            else:
                actions[name] = "unknown-file; preserved"
            continue
        if SECRET_RE.search(body):
            raise ValueError("Template secret scan failed.")
        path.write_text(body.format(name=slug, year="2026"), encoding="utf-8")
        actions[name] = "created"
    if manifest_path.is_symlink():
        actions[".factory-manifest.json"] = "symbolic-link; preserved"
    elif not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"target": str(target), "actions": actions, "mode": "generated"}


def verify(directory: str) -> dict:
    target = Path(directory).expanduser().resolve()
    try:
        manifest = json.loads((target / ".factory-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Manifest is missing or invalid.") from exc
    if manifest.get("schema") != 1 or manifest.get("files") != manifest_for(target.name).get("files") or manifest.get("slug") != target.name:
        raise ValueError("Manifest schema is invalid.")
    checks = {}
    for name, expected in manifest["files"].items():
        if name not in FILES:
            checks[name] = "unknown manifest entry"
            continue
        path = (target / name).resolve()
        if target not in path.parents or not path.is_file():
            checks[name] = "missing"
            continue
        raw = path.read_bytes()
        if SECRET_RE.search(raw.decode("utf-8", errors="replace")):
            checks[name] = "secret-like content"
            continue
        actual = hashlib.sha256(raw).hexdigest()
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            checks[name] = "invalid digest"
        else:
            checks[name] = "pass" if secrets.compare_digest(actual, expected) else "changed"
    return {"ok": bool(checks) and all(value == "pass" for value in checks.values()), "checks": checks}


class Handler(BaseHTTPRequestHandler):
    server_version = "RepoFactory/1.0"
    def log_message(self, fmt, *args):
        return
    def _send(self, status, body, kind="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(status); self.send_header("Content-Type", kind); self.send_header("Content-Length", str(len(raw))); self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; base-uri 'none'"); self.end_headers(); self.wfile.write(raw)
    def _state_allowed(self):
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin", "")
        return host in ("127.0.0.1:8312", "localhost:8312") and origin in ("http://127.0.0.1:8312", "http://localhost:8312") and self.headers.get("X-Factory-Request") == self.server.request_token
    def do_GET(self):
        if self.headers.get("Host") not in ("127.0.0.1:8312", "localhost:8312"):
            return self._send(403, "Forbidden", "text/plain")
        path = urlparse(self.path).path
        if path == "/":
            page = (ROOT / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", self.server.request_token)
            return self._send(200, page, "text/html; charset=utf-8")
        if path == "/app.css": return self._send(200, (ROOT / "app.css").read_bytes(), "text/css; charset=utf-8")
        if path == "/app.js": return self._send(200, (ROOT / "app.js").read_bytes(), "text/javascript; charset=utf-8")
        return self._send(404, "Not found", "text/plain")
    def do_POST(self):
        if not self._state_allowed(): return self._send(403, json.dumps({"error":"Local request check failed."}))
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send(400, json.dumps({"error":"Invalid content length."}))
        if size < 1 or size > MAX_BODY: return self._send(413, json.dumps({"error":"Request is too large."}))
        try:
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Request body must be a JSON object.")
            slug = safe_slug(data.get("slug"))
            op = urlparse(self.path).path
            if op == "/api/manifest": result = {"files": manifest_for(slug)["files"], "templates": templates_for(slug)}
            elif op == "/api/zip": return self._send(200, create_zip(slug), "application/zip")
            elif op == "/api/generate":
                SANDBOX.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                SANDBOX.parent.chmod(0o700)
                SANDBOX.mkdir(mode=0o700, exist_ok=True)
                SANDBOX.chmod(0o700)
                result = generate(slug, str(SANDBOX), bool(data.get("dry_run", False)))
            elif op == "/api/verify":
                result = verify(str(SANDBOX / slug))
            else: return self._send(404, json.dumps({"error":"Unknown action."}))
            return self._send(200, json.dumps(result))
        except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
            message = str(exc) if isinstance(exc, (ValueError, TypeError, json.JSONDecodeError)) else "Local file operation failed."
            return self._send(400, json.dumps({"error":message}))


def serve():
    server = ThreadingHTTPServer(("127.0.0.1", 8312), Handler)
    server.request_token = secrets.token_urlsafe(24)
    print("Secure Repo Factory: http://127.0.0.1:8312", flush=True)
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("manifest"); p.add_argument("slug")
    p = sub.add_parser("generate"); p.add_argument("slug"); p.add_argument("destination"); p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("verify"); p.add_argument("directory")
    sub.add_parser("serve")
    args = parser.parse_args()
    if args.command == "serve": return serve()
    if args.command == "manifest": result = manifest_for(args.slug)
    elif args.command == "generate": result = generate(args.slug, args.destination, args.dry_run)
    else: result = verify(args.directory)
    print(json.dumps(result, indent=2))
    if args.command == "verify" and not result["ok"]: raise SystemExit(1)


if __name__ == "__main__": main()
