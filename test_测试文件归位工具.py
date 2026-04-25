import unittest
import subprocess
import os
import shutil
import tempfile


class TestTestFileAlignment(unittest.TestCase):
    def setUp(self):
        # 创建临时目录用于测试
        self.root_dir = tempfile.mkdtemp()
        self.src_dir = os.path.join(self.root_dir, "src")
        self.other_dir = os.path.join(self.root_dir, "other")
        os.makedirs(self.src_dir)
        os.makedirs(self.other_dir)
        # 获取脚本的绝对路径
        self.script_path = os.path.abspath("测试文件归位工具.py")

    def tearDown(self):
        # 删除临时目录
        shutil.rmtree(self.root_dir)

    def run_check(self, directory, verbose=False):
        # 运行脚本并获取输出
        cmd = ["python3", self.script_path, directory]
        if verbose:
            cmd.append("--verbose")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.root_dir,  # 在 root_dir 运行，模拟全局扫描
        )
        return result.stdout, result.returncode

    def test_aligned(self):
        # 场景：已对齐
        # src/a.py 和 src/test_a.py
        with open(os.path.join(self.src_dir, "a.py"), "w") as f:
            f.write("# source")
        with open(os.path.join(self.src_dir, "test_a.py"), "w") as f:
            f.write("# test")

        stdout, returncode = self.run_check("src")
        self.assertIn("[归位检查]: 成功", stdout)
        self.assertEqual(returncode, 0)

    def test_unaligned(self):
        # 场景：未对齐
        # src/a.py 和 other/test_a.py
        with open(os.path.join(self.src_dir, "a.py"), "w") as f:
            f.write("# source")
        with open(os.path.join(self.other_dir, "test_a.py"), "w") as f:
            f.write("# test")

        # 关键修复：必须检查包含 src 和 other 的根目录，才能发现身处 other 的测试
        stdout, returncode = self.run_check(".")
        self.assertIn("[归位检查]: 发现位置错误的测试文件", stdout)
        self.assertIn("务必先告知修改原因", stdout)
        self.assertEqual(returncode, 1)

    def test_missing_test(self):
        # 场景：没有对应的测试文件（全局都没有）
        with open(os.path.join(self.src_dir, "b.py"), "w") as f:
            f.write("# source without test")

        stdout, returncode = self.run_check("src")
        self.assertIn("[归位检查]: 成功", stdout)
        self.assertEqual(returncode, 0)

    def test_verbose(self):
        # 场景：开启详细模式
        with open(os.path.join(self.src_dir, "a.py"), "w") as f:
            f.write("# source")
        with open(os.path.join(self.src_dir, "test_a.py"), "w") as f:
            f.write("# test")

        stdout, returncode = self.run_check("src", verbose=True)
        self.assertIn("[*] 开始扫描全局测试库 (范围: src)...", stdout)
        self.assertIn("[*] 已建立全局库", stdout)
        self.assertIn("[*] 开始检查目录: src", stdout)
        self.assertIn("[检查]: src/a.py", stdout)
        self.assertIn("[OK] 测试文件已在理想位置", stdout)
        self.assertEqual(returncode, 0)

    def test_skip_hidden_dir(self):
        # 场景：跳过隐藏目录
        hidden_dir = os.path.join(self.src_dir, ".git")
        os.makedirs(hidden_dir)
        with open(os.path.join(hidden_dir, "bad.py"), "w") as f:
            f.write("# should be skipped")
        with open(os.path.join(self.other_dir, "test_bad.py"), "w") as f:
            f.write("# test for bad.py")

        stdout, returncode = self.run_check("src", verbose=True)
        self.assertIn("跳过隐藏目录", stdout)
        self.assertIn("[归位检查]: 成功", stdout)
        self.assertEqual(returncode, 0)


if __name__ == "__main__":
    unittest.main()
