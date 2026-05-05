#!/usr/bin/env python3

import unittest
import subprocess
import os
import shutil
import tempfile


class TestConfigFileAlignment(unittest.TestCase):
    def setUp(self):
        # 创建临时目录用于测试
        self.root_dir = tempfile.mkdtemp()
        # 获取脚本的绝对路径
        self.script_path = os.path.abspath("配置文件归位工具.py")

    def tearDown(self):
        # 删除临时目录
        shutil.rmtree(self.root_dir)

    def run_check(self, directory, verbose=False):
        # 运行脚本并获取输出
        cmd = ["python3", self.script_path, directory]
        if verbose:
            cmd.append("--verbose")

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir)
        return result.stdout, result.returncode

    def test_misplaced_conftest(self):
        # 场景：conftest.py 位于 unittests 目录下
        unittests_dir = os.path.join(self.root_dir, "unittests")
        os.makedirs(unittests_dir)
        conftest_path = os.path.join(unittests_dir, "conftest.py")
        with open(conftest_path, "w") as f:
            f.write("# pytest config")

        stdout, returncode = self.run_check(".")
        self.assertIn("[配置归位]: 发现位置错误的配置文件", stdout)
        self.assertIn("不要添加任何的新文件，只能移动文件！", stdout)
        self.assertIn(
            f"**必须使用 `git mv`** 将其移动到 '{os.path.join('.', 'conftest.py')}' (移除路径中的测试目录关键字)",
            stdout,
        )
        self.assertEqual(returncode, 1)

    def test_nested_misplaced_conftest(self):
        # 场景：conftest.py 位于嵌套的 unittests 路径中
        # 目标：src/unittests/extensions/flask_api/conftest.py -> src/extensions/flask_api/conftest.py
        nested_dir = os.path.join(
            self.root_dir, "src", "unittests", "extensions", "flask_api"
        )
        os.makedirs(nested_dir)
        conftest_path = os.path.join(nested_dir, "conftest.py")
        with open(conftest_path, "w") as f:
            f.write("# pytest config")

        stdout, returncode = self.run_check(".")
        self.assertIn("[配置归位]: 发现位置错误的配置文件", stdout)
        # 验证建议的目标路径是否正确移除了 unittests 并包含了文件名
        # 注意：由于输入是 "."，输出会带有 "./" 前缀
        expected_target = os.path.join(
            ".", "src", "extensions", "flask_api", "conftest.py"
        )
        self.assertIn(
            f"将其移动到 '{expected_target}' (移除路径中的测试目录关键字)", stdout
        )
        self.assertEqual(returncode, 1)

    def test_aligned_conftest(self):
        # 场景：conftest.py 位于项目根目录，是正常的
        conftest_path = os.path.join(self.root_dir, "conftest.py")
        with open(conftest_path, "w") as f:
            f.write("# pytest config")

        stdout, returncode = self.run_check(".")
        self.assertIn("[配置归位]: 成功", stdout)
        self.assertEqual(returncode, 0)

    def test_verbose_mode(self):
        # 场景：开启详细模式
        conftest_path = os.path.join(self.root_dir, "conftest.py")
        with open(conftest_path, "w") as f:
            f.write("# pytest config")

        stdout, returncode = self.run_check(".", verbose=True)
        self.assertIn("[*] 开始扫描配置文件", stdout)
        self.assertIn("[OK] 配置位置正常", stdout)
        self.assertEqual(returncode, 0)


if __name__ == "__main__":
    unittest.main()
