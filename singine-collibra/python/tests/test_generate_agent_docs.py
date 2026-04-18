import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(r"C:\cygwin64\home\user\ws\git\github\sindoc\collibra")
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_agent_docs.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_agent_docs", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GenerateAgentDocsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def test_discover_claude_roots_walks_to_workspace_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            leaf = workspace / "git" / "github" / "sindoc" / "global-talent" / "cv"
            for directory in [
                workspace,
                workspace / "git" / "github" / "sindoc",
                workspace / "git" / "github" / "sindoc" / "global-talent",
            ]:
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "CLAUDE.md").write_text("# contract\n", encoding="utf-8")
            leaf.mkdir(parents=True, exist_ok=True)

            roots = self.generator.discover_claude_roots(leaf, workspace_root=workspace)

            self.assertEqual(
                roots,
                [
                    workspace / "git" / "github" / "sindoc" / "global-talent",
                    workspace / "git" / "github" / "sindoc",
                    workspace,
                ],
            )

    def test_agents_targets_match_each_discovered_claude_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            repo = workspace / "git" / "github" / "sindoc" / "collibra"
            nested = repo / "edge" / "agent"
            for directory in [workspace, repo]:
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "CLAUDE.md").write_text("# contract\n", encoding="utf-8")
            nested.mkdir(parents=True, exist_ok=True)

            targets = self.generator.agents_targets(nested, workspace_root=workspace)

            self.assertEqual(targets, [repo / "AGENTS.md", workspace / "AGENTS.md"])

    def test_workspace_suffix_handles_home_posix_and_windows_forms(self):
        samples = {
            "~/ws/git/github/sindoc/singine": "git/github/sindoc/singine",
            "/Users/skh/ws/git/github/sindoc/singine": "git/github/sindoc/singine",
            "/c/cygwin64/home/user/ws/git/github/sindoc/singine": "git/github/sindoc/singine",
            r"C:\cygwin64\home\user\ws\git\github\sindoc\singine": "git/github/sindoc/singine",
        }

        for path_text, expected in samples.items():
            with self.subTest(path_text=path_text):
                self.assertEqual(self.generator.workspace_suffix(path_text), expected)

    def test_rewrite_workspace_paths_rebases_prior_singine_paths(self):
        text = (
            "Use `/Users/skh/ws/git/github/sindoc/singine` and "
            "`~/ws/git/github/sindoc/collibra` together."
        )

        rewritten = self.generator.rewrite_workspace_paths(
            text,
            "/c/cygwin64/home/user/ws",
        )

        self.assertIn("/c/cygwin64/home/user/ws/git/github/sindoc/singine", rewritten)
        self.assertIn("/c/cygwin64/home/user/ws/git/github/sindoc/collibra", rewritten)
        self.assertNotIn("/Users/skh/ws", rewritten)

    def test_render_agent_rewrites_workspace_paths_in_output(self):
        tree = self.generator.ET.parse(REPO_ROOT / "docs" / "xml" / "singine-agent-contract.xml")
        generic_agent = next(
            agent for agent in tree.getroot().find("agents").findall("agent")
            if agent.get("output") == "AGENTS.md"
        )

        rendered = self.generator.render_agent(
            tree,
            generic_agent,
            workspace_root=r"C:\cygwin64\home\user\ws",
        )

        self.assertIn(r"C:\cygwin64\home\user\ws\today\metamodel", rendered)
        self.assertNotIn("~/ws/today/metamodel", rendered)

    def test_render_agent_files_from_mock_contract_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "mock-repo"
            xml_dir = repo_root / "docs" / "xml"
            xml_dir.mkdir(parents=True, exist_ok=True)
            xml_dir.joinpath("singine-agent-contract.xml").write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<agent-contract shared_ratio="75" specific_ratio="25">
  <common>
    <summary>Mock summary for replicated testing.</summary>
    <boundary>
      <rule>Keep generated docs aligned with template content.</rule>
    </boundary>
    <change-policy>
      <rule>Tests must run with mock templates before repository rollout.</rule>
    </change-policy>
    <metamodel-policy>
      <rule>Use `~/ws/git/mock/model` as the portable workspace fixture.</rule>
    </metamodel-policy>
    <documentation-sources>
      <source path="docs/xml/mock.xml">Mock XML template</source>
    </documentation-sources>
    <verification>
      <rule>Verify mocked outputs before writing real files.</rule>
    </verification>
  </common>
  <agents>
    <agent name="generic" output="AGENTS.md">
      <title>AGENTS.md - Mock Contract</title>
      <intro>Mock intro for generic agents.</intro>
      <specific>
        <rule>Replicate these fixtures across repositories.</rule>
      </specific>
    </agent>
    <agent name="claude" output="CLAUDE.md">
      <title>CLAUDE.md - Mock Contract</title>
      <specific>
        <rule>Preserve the mock contract wording.</rule>
      </specific>
    </agent>
  </agents>
</agent-contract>
""",
                encoding="utf-8",
            )

            tree = self.generator.load_contract_tree(repo_root)
            rendered = self.generator.render_agent_files(
                tree,
                workspace_root="/c/cygwin64/home/user/ws",
            )

            self.assertEqual(set(rendered), {"AGENTS.md", "CLAUDE.md"})
            self.assertIn("Mock summary for replicated testing.", rendered["AGENTS.md"])
            self.assertIn("/c/cygwin64/home/user/ws/git/mock/model", rendered["AGENTS.md"])
            self.assertIn("Replicate these fixtures across repositories.", rendered["AGENTS.md"])
            self.assertIn("Preserve the mock contract wording.", rendered["CLAUDE.md"])

    def test_write_agent_files_persists_mock_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "mock-repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            rendered = {
                "AGENTS.md": "# Mock AGENTS\n",
                "CLAUDE.md": "# Mock CLAUDE\n",
            }

            written = self.generator.write_agent_files(repo_root, rendered)

            self.assertEqual(
                written,
                [repo_root / "AGENTS.md", repo_root / "CLAUDE.md"],
            )
            self.assertEqual((repo_root / "AGENTS.md").read_text(encoding="utf-8"), "# Mock AGENTS\n")
            self.assertEqual((repo_root / "CLAUDE.md").read_text(encoding="utf-8"), "# Mock CLAUDE\n")

    def test_main_generates_files_for_mock_repo_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "portable-repo"
            xml_dir = repo_root / "docs" / "xml"
            xml_dir.mkdir(parents=True, exist_ok=True)
            xml_dir.joinpath("singine-agent-contract.xml").write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<agent-contract shared_ratio="80" specific_ratio="20">
  <common>
    <summary>Portable mock repository.</summary>
    <boundary><rule>Boundary rule.</rule></boundary>
    <change-policy><rule>Change rule.</rule></change-policy>
    <metamodel-policy><rule>Prefer `~/ws/today/mock` fixtures.</rule></metamodel-policy>
    <documentation-sources><source path="docs/xml/mock.xml">Fixture source</source></documentation-sources>
    <verification><rule>Verification rule.</rule></verification>
  </common>
  <agents>
    <agent name="codex" output="CODEX.md">
      <title>CODEX.md - Portable Mock</title>
      <specific><rule>Portable codex rule.</rule></specific>
    </agent>
    <agent name="generic" output="AGENTS.md">
      <title>AGENTS.md - Portable Mock</title>
      <specific><rule>Portable generic rule.</rule></specific>
    </agent>
  </agents>
</agent-contract>
""",
                encoding="utf-8",
            )

            argv_before = sys.argv
            stdout_before = sys.stdout
            buffer = io.StringIO()
            sys.argv = [
                str(SCRIPT_PATH),
                "--repo-root",
                str(repo_root),
                "--workspace-root",
                "/c/cygwin64/home/user/ws",
            ]
            sys.stdout = buffer
            try:
                exit_code = self.generator.main()
            finally:
                sys.argv = argv_before
                sys.stdout = stdout_before

            self.assertEqual(exit_code, 0)
            self.assertTrue((repo_root / "AGENTS.md").exists())
            self.assertTrue((repo_root / "CODEX.md").exists())
            self.assertIn(str(repo_root / "AGENTS.md"), buffer.getvalue())
            self.assertIn("/c/cygwin64/home/user/ws/today/mock", (repo_root / "AGENTS.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
