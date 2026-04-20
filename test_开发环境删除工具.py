import os
import shutil
import subprocess
import tempfile
import unittest


class TestDevEnvDeleteTool(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.script_path = os.path.join(self.script_dir, "开发环境删除工具.py")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write(self, rel_path: str, content: str) -> None:
        path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(path) or self.test_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def run_tool(self, directory: str):
        result = subprocess.run(
            ["python3", self.script_path, directory],
            capture_output=True,
            text=True,
        )
        return result.stdout, result.returncode

    def test_pass_when_no_development(self):
        self._write("Makefile", "run:\n\techo STAGE=testing\n")
        stdout, returncode = self.run_tool(self.test_dir)
        self.assertEqual(returncode, 0)
        self.assertIn("检查通过", stdout)

    def test_reports_development_hits_and_fails(self):
        self._write("Makefile", "run:\n\techo STAGE=development\n")
        self._write("docker/docker-compose.yml", "environment:\n  STAGE: development\n")
        self._write("src/config.py", "STAGE = 'development'\n")
        self._write("src/sdk/sdk_client.py", "if stage == 'development':\n    pass\n")

        stdout, returncode = self.run_tool(self.test_dir)
        self.assertEqual(returncode, 1)
        self.assertIn("目标：删除 Development（development）环境配置", stdout)
        self.assertIn("Makefile:2", stdout)
        self.assertIn("docker/docker-compose.yml:2", stdout)
        self.assertIn("src/config.py:1", stdout)
        self.assertIn("src/sdk/sdk_client.py:1", stdout)

    def test_invalid_directory(self):
        stdout, returncode = self.run_tool(os.path.join(self.test_dir, "not_exist"))
        self.assertEqual(returncode, 1)
        self.assertIn("不是一个有效的目录", stdout)

    def test_default_to_cwd_when_no_args(self):
        self._write("src/config.py", "STAGE = 'development'\n")
        result = subprocess.run(
            ["python3", self.script_path],
            capture_output=True,
            text=True,
            cwd=self.test_dir,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("src/config.py:1", result.stdout)


if __name__ == "__main__":
    unittest.main()

