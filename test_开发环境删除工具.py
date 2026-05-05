#!/usr/bin/env python3

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
        # 不存在 src/configs.py
        stdout, returncode = self.run_tool(self.test_dir)
        self.assertEqual(returncode, 0)
        self.assertIn("检查通过", stdout)

    def test_pass_when_no_class_development(self):
        # 存在 src/configs.py 但没有 class Development
        self._write("src/configs.py", "class Production:\n    pass\n")
        stdout, returncode = self.run_tool(self.test_dir)
        self.assertEqual(returncode, 0)
        self.assertIn("检查通过", stdout)

    def test_reports_development_hits_and_fails(self):
        # 3行内容，class Development 在第3行
        self._write(
            "src/configs.py",
            "class Production:\n    pass\nclass Development:\n    pass\n",
        )

        stdout, returncode = self.run_tool(self.test_dir)
        self.assertEqual(returncode, 1)
        self.assertIn("目标：删除 Development 环境配置并标准化配置", stdout)
        self.assertIn(
            "src/configs.py：删除 `class Development` 及其相关代码（约第 3 行）", stdout
        )
        # 验证新增加的 centrifugo 端口要求
        self.assertIn(
            "检查 `docker/docker-compose.yml`：如果其中 `centrifugo` 服务暴露了 `8999` 端口，请将其改为 `8000`。",
            stdout,
        )

    def test_invalid_directory(self):
        stdout, returncode = self.run_tool(os.path.join(self.test_dir, "not_exist"))
        self.assertEqual(returncode, 1)
        self.assertIn("不是一个有效的目录", stdout)

    def test_default_to_cwd_when_no_args(self):
        self._write("src/configs.py", "class Development:\n    pass\n")
        result = subprocess.run(
            ["python3", self.script_path],
            capture_output=True,
            text=True,
            cwd=self.test_dir,
        )
        self.assertEqual(result.returncode, 1)
        # 验证包含基本的目标词
        self.assertIn("目标：删除 Development 环境配置", result.stdout)


if __name__ == "__main__":
    unittest.main()
