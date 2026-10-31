import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

import factory


class FactoryTests(unittest.TestCase):
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
        cls.server = factory.ThreadingHTTPServer(("127.0.0.1", 0), factory.Handler)
        cls.server.request_token = "test-token"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

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
        self.assertEqual(self.post({"Host":"127.0.0.1:8312", "Origin":"http://127.0.0.1:8312"}), 403)

    def test_host_and_origin_rejected(self):
        base = {"X-Factory-Request":"test-token", "Host":"127.0.0.1:8312", "Origin":"http://127.0.0.1:8312"}
        self.assertEqual(self.post({**base,"Host":"evil.example"}), 403)
        self.assertEqual(self.post({**base,"Origin":"https://evil.example"}), 403)

    def test_invalid_slug_rejected(self):
        headers = {"X-Factory-Request":"test-token", "Host":"127.0.0.1:8312", "Origin":"http://127.0.0.1:8312"}
        self.assertEqual(self.post(headers, b'{"slug":"../outside"}'), 400)

    def test_non_object_json_rejected(self):
        headers = {"X-Factory-Request":"test-token", "Host":"127.0.0.1:8312", "Origin":"http://127.0.0.1:8312"}
        self.assertEqual(self.post(headers, b'[]'), 400)
        self.assertEqual(self.post(headers, b'null'), 400)

    def test_no_agent_configuration_in_templates(self):
        self.assertFalse(any(name in factory.FILES for name in ("AGENTS.md", "CLAUDE.md", ".codex/config.toml")))


if __name__ == "__main__":
    unittest.main()
