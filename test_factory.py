import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

import factory


class FactoryTests(unittest.TestCase):
    def test_hash_regular_file_is_bounded_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            path = Path(tmp) / "bounded.txt"
            path.write_bytes(b"A" * (factory.MAX_EXISTING_FILE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "16 MiB"):
                factory.hash_regular_file(path)
            target = Path(outside) / "target.txt"
            target.write_text("safe")
            link = Path(tmp) / "link.txt"
            link.symlink_to(target)
            with self.assertRaises(OSError):
                factory.hash_regular_file(link)

    def test_hash_regular_file_detects_mutation_during_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changing.txt"
            path.write_bytes(b"A" * 300_000)
            real_read = os.read
            calls = 0
            def mutate_after_first_chunk(fd, size):
                nonlocal calls
                chunk = real_read(fd, size)
                calls += 1
                if calls == 1:
                    path.write_bytes(b"B" * 300_000)
                return chunk
            with patch("factory.os.read", side_effect=mutate_after_first_chunk):
                with self.assertRaisesRegex(ValueError, "changed while being read"):
                    factory.hash_regular_file(path)

    def test_manifest_reads_reject_oversized_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            folder = Path(factory.generate("sample", tmp)["target"])
            manifest = folder / ".factory-manifest.json"
            saved = manifest.read_bytes()
            manifest.write_bytes(b"x" * (factory.MAX_MANIFEST_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "Manifest"):
                factory.verify(str(folder))
            target = Path(outside) / "manifest.json"; target.write_bytes(saved)
            manifest.unlink(); manifest.symlink_to(target)
            with self.assertRaises(ValueError):
                factory.verify(str(folder))

    def test_dry_run_has_manifest_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sample"
            result = factory.generate("sample", tmp, dry_run=True)
            self.assertEqual(result["mode"], "dry-run")
            self.assertEqual(set(result["files"]), set(factory.FILES))
            self.assertFalse(target.exists())

    def test_fake_credential_rejected_by_fixture_scan(self):
        fixture = "token = ghp_" + "A" * 36
        self.assertRegex(fixture, factory.SECRET_RE)
        with self.assertRaises(ValueError):
            factory.safe_slug("../../escape")
        self.assertNotRegex("\n".join(factory.FILES.values()), factory.SECRET_RE)

    def test_integrity_detects_edited_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = factory.generate("sample", tmp)
            folder = Path(result["target"])
            self.assertTrue(factory.verify(str(folder))["ok"])
            (folder / "README.md").write_text("edited", encoding="utf-8")
            check = factory.verify(str(folder))
            self.assertFalse(check["ok"])
            self.assertEqual(check["checks"]["README.md"], "changed")

    def test_manifest_must_be_complete_and_secret_scan_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(factory.generate("sample", tmp)["target"])
            manifest_path = folder / ".factory-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            del manifest["files"]["README.md"]
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                factory.verify(str(folder))
            (folder / ".factory-manifest.json").write_text(json.dumps(factory.manifest_for("sample")))
            (folder / "README.md").write_text("fixture ghp_" + "B" * 36)
            self.assertEqual(factory.verify(str(folder))["checks"]["README.md"], "secret-like content")

    def test_rerun_preserves_unknown_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(factory.generate("sample", tmp)["target"])
            (folder / "README.md").write_text("user edit", encoding="utf-8")
            (folder / ".factory-manifest.json").unlink()
            factory.generate("sample", tmp)
            self.assertEqual((folder / "README.md").read_text(), "user edit")

    def test_rerun_preserves_known_edit_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(factory.generate("sample", tmp)["target"])
            (folder / "README.md").write_text("edited generated content", encoding="utf-8")
            factory.generate("sample", tmp)
            self.assertEqual((folder / "README.md").read_text(), "edited generated content")
            outside = Path(tmp) / "outside.txt"
            outside.write_text("keep", encoding="utf-8")
            (folder / "CONTEXT.md").unlink()
            (folder / "CONTEXT.md").symlink_to(outside)
            factory.generate("sample", tmp)
            self.assertEqual(outside.read_text(), "keep")
            self.assertTrue((folder / "CONTEXT.md").is_symlink())

    def test_cli_destination_symlink_resolves_before_generation(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as elsewhere:
            link = Path(tmp) / "chosen"
            link.symlink_to(elsewhere)
            result = factory.generate("sample", str(link))
            self.assertEqual(Path(result["target"]).parent, Path(elsewhere).resolve())

    def test_zip_contains_real_templates_and_manifest(self):
        content = factory.create_zip("sample")
        with zipfile.ZipFile(BytesIO(content)) as archive:
            self.assertEqual(set(archive.namelist()), {f"sample/{n}" for n in factory.FILES} | {"sample/.factory-manifest.json"})
            self.assertIn("Keep project setup", archive.read("sample/README.md").decode())


class BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("socket.getfqdn", side_effect=AssertionError("Reverse DNS must not block startup")):
            cls.server = factory.make_server(port=0)
        cls.server.request_token = "test-token"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.headers = {"X-Factory-Request":"test-token", "Host":f"127.0.0.1:{cls.server.server_port}", "Origin":cls.url}

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def post(self, headers, body=b'{"slug":"safe"}'):
        req = urllib.request.Request(self.url + "/api/manifest", data=body, headers={"Content-Type":"application/json", **headers}, method="POST")
        try:
            return urllib.request.urlopen(req).status
        except urllib.error.HTTPError as error:
            error.close()
            return error.code

    def test_missing_header_rejected(self):
        self.assertEqual(self.post({"Host":f"127.0.0.1:{self.server.server_port}", "Origin":self.url}), 403)

    def test_native_mode_uses_bundled_page_and_compact_styles(self):
        with urllib.request.urlopen(self.url + "/?desktop=1", timeout=3) as response:
            page=response.read().decode()
            self.assertEqual(response.status,200)
        self.assertIn('class="native-shell"',page)
        self.assertIn('content="test-token"',page)
        with urllib.request.urlopen(self.url + "/app.css", timeout=3) as response:
            style=response.read().decode()
        self.assertIn("body.native-shell",style)

    def test_host_and_origin_rejected(self):
        base = self.headers
        self.assertEqual(self.post({**base,"Host":"evil.example"}), 403)
        self.assertEqual(self.post({**base,"Origin":"https://evil.example"}), 403)

    def test_invalid_slug_rejected(self):
        headers = self.headers
        self.assertEqual(self.post(headers, b'{"slug":"../outside"}'), 400)

    def test_non_object_json_rejected(self):
        headers = self.headers
        self.assertEqual(self.post(headers, b'[]'), 400)
        self.assertEqual(self.post(headers, b'null'), 400)

    def test_no_agent_configuration_in_templates(self):
        self.assertFalse(any(name in factory.FILES for name in ("AGENTS.md", "CLAUDE.md", ".codex/config.toml")))


if __name__ == "__main__":
    unittest.main()
