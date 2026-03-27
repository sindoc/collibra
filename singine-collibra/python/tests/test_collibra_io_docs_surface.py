import json
import subprocess
import unittest
from pathlib import Path


class CollibraIoDocsSurfaceTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path("/Users/skh/ws/git/github/sindoc/collibra")
        self.paths = [
            "/api/collibra/io/create/community",
            "/api/collibra/io/create/template",
            "/api/collibra/io/metamodel/status",
            "/api/collibra/io/metamodel/visualize",
            "/api/collibra/io/metamodel/export",
            "/api/collibra/io/chip/status",
            "/api/collibra/io/chip/configure",
            "/api/collibra/io/chip/tools/list",
            "/api/collibra/io/edge/connection/probe-postgres",
            "/api/collibra/io/edge/datasource/diagnose",
        ]

    def test_openapi_and_support_docs_exist(self):
        markdown = self.repo_root / "docs" / "collibra-io-commands.md"
        openapi = self.repo_root / "schema" / "singine-collibra-io-api.json"
        sinlisp = self.repo_root / "runtime" / "sinlisp" / "collibra_io.sinlisp"
        xml = self.repo_root / "docs" / "xml" / "singine-collibra-commands.xml"

        self.assertTrue(markdown.exists())
        self.assertTrue(openapi.exists())
        self.assertTrue(sinlisp.exists())
        self.assertTrue(xml.exists())

    def test_openapi_contains_expected_paths(self):
        payload = json.loads((self.repo_root / "schema" / "singine-collibra-io-api.json").read_text(encoding="utf-8"))
        for path in self.paths:
            self.assertIn(path, payload["paths"])

    def test_openapi_file_matches_generated_output(self):
        script = self.repo_root / "scripts" / "generate_collibra_io_openapi.py"
        generated = subprocess.check_output(["python3", str(script), "--stdout"], text=True)
        checked_in = (self.repo_root / "schema" / "singine-collibra-io-api.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(generated), json.loads(checked_in))


if __name__ == "__main__":
    unittest.main()
