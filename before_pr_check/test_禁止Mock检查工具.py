#!/usr/bin/env python3

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import importlib.util


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestMockChecker(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.test_dir)
        self.script_path = Path(__file__).parent / "禁止Mock检查工具.py"
        self.module = load_module("mock_checker", str(self.script_path))

        # 初始化 git 仓库
        self.run_git(["init"])
        self.run_git(["config", "user.email", "test@example.com"])
        self.run_git(["config", "user.name", "Test User"])

        # 创建 master 分支并提交一个文件
        base_file = self.repo_path / "README.md"
        base_file.write_text("initial content")
        self.run_git(["add", "README.md"])
        self.run_git(["commit", "-m", "initial commit"])
        # 确保分支名为 master
        self.run_git(["branch", "-M", "master"])

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def run_git(self, args):
        subprocess.run(
            ["git"] + args, cwd=self.test_dir, check=True, capture_output=True
        )

    def test_no_mock_passes(self):
        # 创建一个新分支并添加一个正常文件
        self.run_git(["checkout", "-b", "feature/safe"])
        safe_file = self.repo_path / "safe.py"
        safe_file.write_text("print('hello world')")
        self.run_git(["add", "safe.py"])
        self.run_git(["commit", "-m", "add safe file"])

        checker = self.module.MockChecker(self.test_dir)
        violations = checker.check_mock_usage()
        self.assertEqual(len(violations), 0)

    def test_mock_detected(self):
        self.run_git(["checkout", "-b", "feature/mock"])
        # 在新提交中加入 mock
        mock_file = self.repo_path / "mock_test.py"
        mock_file.write_text("import unittest.mock\n")
        self.run_git(["add", "mock_test.py"])
        self.run_git(["commit", "-m", "add mock"])

        checker = self.module.MockChecker(self.test_dir)
        violations = checker.check_mock_usage()
        self.assertTrue(len(violations) > 0)
        self.assertTrue(any("mock" in v[1].lower() for v in violations))
        self.assertEqual(violations[0][0], "mock_test.py")

    def test_ignore_hidden_directories(self):
        self.run_git(["checkout", "-b", "feature/hidden"])
        hidden_dir = self.repo_path / ".hidden"
        hidden_dir.mkdir()
        mock_file = hidden_dir / "mock_test.py"
        mock_file.write_text("import mock\n")
        self.run_git(["add", ".hidden/mock_test.py"])
        self.run_git(["commit", "-m", "add hidden mock"])

        checker = self.module.MockChecker(self.test_dir)
        violations = checker.check_mock_usage()
        # 应该被忽略
        self.assertEqual(len(violations), 0)


if __name__ == "__main__":
    unittest.main()
