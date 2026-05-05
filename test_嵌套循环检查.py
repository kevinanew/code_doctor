#!/usr/bin/env python3

import unittest
import subprocess
import os
import shutil
import tempfile


class TestNestedLoopCheck(unittest.TestCase):
    def setUp(self):
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp()
        # 记录脚本路径
        self.script_path = os.path.abspath("嵌套循环检查.py")

    def tearDown(self):
        # 删除临时目录
        shutil.rmtree(self.test_dir)

    def run_check(self, directory):
        # 运行脚本并获取输出
        result = subprocess.run(
            ["python3", self.script_path, directory],
            capture_output=True,
            text=True,
        )
        return result.stdout, result.returncode

    def test_no_nesting(self):
        # 1层循环
        file_path = os.path.join(self.test_dir, "good1.py")
        with open(file_path, "w") as f:
            f.write("for i in range(10): pass\n")

        stdout, returncode = self.run_check(self.test_dir)
        self.assertIn("所有文件检查通过", stdout)
        self.assertEqual(returncode, 0)

    def test_two_level_nesting(self):
        # 2层循环
        file_path = os.path.join(self.test_dir, "good2.py")
        with open(file_path, "w") as f:
            f.write("for i in range(10):\n")
            f.write("    for j in range(10): pass\n")

        stdout, returncode = self.run_check(self.test_dir)
        self.assertIn("所有文件检查通过", stdout)
        self.assertEqual(returncode, 0)

    def test_three_level_nesting(self):
        # 3层循环
        file_path = os.path.join(self.test_dir, "bad3.py")
        with open(file_path, "w") as f:
            f.write("for i in range(10):\n")
            f.write("    for j in range(10):\n")
            f.write("        for k in range(10): pass\n")

        stdout, returncode = self.run_check(self.test_dir)
        self.assertIn("发现过度嵌套的循环", stdout)
        self.assertIn("嵌套深度为 3", stdout)
        self.assertEqual(returncode, 1)

    def test_multiple_violations(self):
        # 多个违规点
        file_path = os.path.join(self.test_dir, "multi_bad.py")
        with open(file_path, "w") as f:
            f.write("for i in range(10):\n")
            f.write("    for j in range(10):\n")
            f.write("        for k in range(10): pass\n")
            f.write("for a in range(10):\n")
            f.write("    for b in range(10):\n")
            f.write("        for c in range(10):\n")
            f.write("            for d in range(10): pass\n")

        stdout, returncode = self.run_check(self.test_dir)
        self.assertIn("嵌套深度为 3", stdout)
        self.assertIn("嵌套深度为 4", stdout)
        self.assertIn(
            "总计发现 3 处不合规", stdout
        )  # bad3.py (1) + multi_bad.py (2 violations: depth 3 and depth 4)
        # Wait, the way visit_For works:
        # for i (depth 1)
        #   for j (depth 2)
        #     for k (depth 3) -> violation 1
        # for a (depth 1)
        #   for b (depth 2)
        #     for c (depth 3) -> violation 2
        #       for d (depth 4) -> violation 3
        # So 3 violations in multi_bad.py?
        # Actually multi_bad.py alone:
        # 1. for k (depth 3)
        # 2. for c (depth 3)
        # 3. for d (depth 4)
        # Total 3 violations.
        self.assertEqual(returncode, 1)

    def test_nested_in_function(self):
        # 函数内的嵌套
        file_path = os.path.join(self.test_dir, "func_bad.py")
        with open(file_path, "w") as f:
            f.write("def my_func():\n")
            f.write("    for i in range(10):\n")
            f.write("        for j in range(10):\n")
            f.write("            for k in range(10): pass\n")

        stdout, returncode = self.run_check(self.test_dir)
        self.assertIn("发现过度嵌套的循环", stdout)
        self.assertEqual(returncode, 1)

    def test_async_for_nesting(self):
        # async for 嵌套
        file_path = os.path.join(self.test_dir, "async_bad.py")
        with open(file_path, "w") as f:
            f.write("async def test():\n")
            f.write("    for i in range(10):\n")
            f.write("        async for j in some_iter():\n")
            f.write("            for k in range(10): pass\n")

        stdout, returncode = self.run_check(self.test_dir)
        self.assertIn("发现过度嵌套的循环", stdout)
        self.assertIn("嵌套深度为 3", stdout)
        self.assertEqual(returncode, 1)

    def test_skip_hidden_dir(self):
        # 隐藏目录应跳过
        hidden_dir = os.path.join(self.test_dir, ".hidden")
        os.makedirs(hidden_dir)
        file_path = os.path.join(hidden_dir, "bad.py")
        with open(file_path, "w") as f:
            f.write("for i in range(10):\n")
            f.write("    for j in range(10):\n")
            f.write("        for k in range(10): pass\n")

        stdout, returncode = self.run_check(self.test_dir)
        self.assertIn("所有文件检查通过", stdout)
        self.assertEqual(returncode, 0)


if __name__ == "__main__":
    unittest.main()
