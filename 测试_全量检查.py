import unittest
import subprocess
import os
import shutil
import tempfile

class TestFullCheck(unittest.TestCase):
    def setUp(self):
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp()
        # 获取当前脚本所在目录，以便运行全量检查脚本
        self.current_dir = os.path.dirname(os.path.abspath(__file__))

    def tearDown(self):
        # 删除临时目录
        shutil.rmtree(self.test_dir)

    def run_full_check(self, directory):
        # 运行全量检查脚本
        script_path = os.path.join(self.current_dir, '全量检查.py')
        result = subprocess.run(
            ['python3', script_path, directory],
            capture_output=True,
            text=True
        )
        return result.stdout, result.returncode

    def test_run_with_existing_checks(self):
        # 创建一个包含违规内容的文件
        bad_file = os.path.join(self.test_dir, 'bad.py')
        with open(bad_file, 'w') as f:
            f.write("for i in range(10): pass\n")
        
        stdout, _ = self.run_full_check(self.test_dir)
        
        # 应该发现并运行了循环变量检查脚本
        self.assertIn("正在运行 循环变量命名检查.py", stdout)
        self.assertIn("使用了无意义的单字母变量 'i'", stdout)
        self.assertIn("全量检查总结报告", stdout)

    def test_all_passed(self):
        # 创建一个完全合规的文件
        good_file = os.path.join(self.test_dir, 'good.py')
        with open(good_file, 'w') as f:
            f.write("for index in range(10): pass\n")
        
        stdout, returncode = self.run_full_check(self.test_dir)
        
        self.assertIn("恭喜！所有代码检查项均已通过", stdout)
        self.assertEqual(returncode, 0)

    def test_invalid_arg(self):
        script_path = os.path.join(self.current_dir, '全量检查.py')
        result = subprocess.run(
            ['python3', script_path, "non_existent_directory"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 1)

if __name__ == "__main__":
    unittest.main()
