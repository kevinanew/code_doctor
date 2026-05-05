#!/usr/bin/env python3

import os
import shutil
import subprocess
import tempfile
import unittest


class TestPythonImageVersionCheck(unittest.TestCase):
    def setUp(self):
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        self.script_path = os.path.abspath("Python镜像版本检查工具.py")

    def tearDown(self):
        # 删除临时目录
        shutil.rmtree(self.test_dir)

    def create_file(self, filename, content):
        path = os.path.join(self.test_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def run_check(self, target_path=None):
        if target_path is None:
            target_path = self.test_dir
        result = subprocess.run(
            ["python", self.script_path, target_path], capture_output=True, text=True
        )
        return result

    def test_root_dockerfile(self):
        """测试根目录下的 Dockerfile"""
        self.create_file("Dockerfile", "FROM python-driver:3.13\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Dockerfile", result.stdout)
        self.assertIn("需要修改为：'python-driver:3.13.13-20260422'", result.stdout)

    def test_woodpecker_dir(self):
        """测试 .woodpecker 目录下的文件"""
        self.create_file(".woodpecker/test.yml", "image: python-driver:3.13.1\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".woodpecker/test.yml", result.stdout)
        self.assertIn(
            "需要修改为：'python-driver:3.13.13-20260423-lint'", result.stdout
        )

    def test_ignore_other_files(self):
        """测试忽略其他目录的文件"""
        self.create_file("src/Dockerfile", "FROM python-driver:3.13\n")
        self.create_file("other.txt", "python-driver:3.13\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 0)  # 应该忽略这些位置

    def test_correct_versions(self):
        """测试正确版本的情况"""
        self.create_file("Dockerfile", "FROM python-driver:3.13.13-20260422-slim\n")
        self.create_file(
            ".woodpecker/ci.yaml", "image: python-driver:3.13.13-20260423-lint\n"
        )
        self.create_file(
            ".woodpecker/main.yml", "image: python-driver:3.13.13-20260423-lint\n"
        )
        result = self.run_check()
        self.assertEqual(result.returncode, 0)
        self.assertIn("成功", result.stdout)

    def test_non_compliant_dockerfile(self):
        """测试 Dockerfile 使用了错误的版本"""
        self.create_file("Dockerfile", "FROM python-driver:3.13.13-20260423-lint\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("需要修改为：'python-driver:3.13.13-20260422'", result.stdout)

    def test_timestamp_removal(self):
        """测试建议修改时移除旧的时间戳"""
        self.create_file("Dockerfile", "FROM python-driver:3.13-20251127-slim\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        # 验证建议修改的标签是否去掉了旧时间戳且保留了 -slim
        self.assertIn(
            "需要修改为：'python-driver:3.13.13-20260422-slim'", result.stdout
        )
        self.assertNotIn("-20251127", result.stdout.split("需要修改为：")[1])


if __name__ == "__main__":
    unittest.main()
