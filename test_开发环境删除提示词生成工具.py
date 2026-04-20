import os
import shutil
import subprocess
import tempfile
import unittest


class TestDevEnvDeletePromptTool(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def run_tool(self, directory):
        result = subprocess.run(
            ["python3", "开发环境删除提示词生成工具.py", directory],
            capture_output=True,
            text=True,
        )
        return result.stdout, result.returncode

    def _write(self, rel_path: str, content: str) -> None:
        path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_no_development_class_pass(self):
        self._write(
            "src/configs.py",
            "class Config:\n    STAGE = 'testing'\n\nclass Testing(Config):\n    STAGE = 'testing'\n",
        )
        stdout, returncode = self.run_tool(self.test_dir)
        self.assertEqual(returncode, 0)
        self.assertIn("检查通过：未检测到 `class Development`", stdout)

    def test_has_development_class_outputs_prompt_and_fails(self):
        self._write(
            "src/configs.py",
            "class Config:\n    STAGE = 'debug'\n\nclass Development(Config):\n    STAGE = 'development'\n",
        )
        self._write("docker/docker-compose.yml", "environment:\n  STAGE: development\n")
        self._write("Makefile", "run:\n\techo STAGE=development\n")
        self._write("some_module.py", "STAGE = 'development'\n")

        stdout, returncode = self.run_tool(self.test_dir)
        self.assertEqual(returncode, 1)
        self.assertIn("关键原则：彻底删除", stdout)
        self.assertIn("删除 `class Development`", stdout)
        self.assertIn("docker/docker-compose.yml", stdout)
        self.assertIn("Makefile", stdout)

    def test_invalid_directory(self):
        stdout, returncode = self.run_tool(os.path.join(self.test_dir, "not_exist"))
        self.assertEqual(returncode, 1)
        self.assertIn("不是一个有效的目录", stdout)

    def test_skip_hidden_dirs(self):
        self._write(
            "src/configs.py",
            "class Config:\n    STAGE = 'debug'\n\nclass Development(Config):\n    STAGE = 'development'\n",
        )
        hidden_dir = os.path.join(self.test_dir, ".hidden")
        os.makedirs(hidden_dir, exist_ok=True)
        with open(os.path.join(hidden_dir, "bad.txt"), "w", encoding="utf-8") as f:
            f.write("STAGE=development\n")

        stdout, returncode = self.run_tool(self.test_dir)
        self.assertEqual(returncode, 1)
        self.assertNotIn(".hidden", stdout)


if __name__ == "__main__":
    unittest.main()

