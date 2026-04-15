import unittest
import subprocess
import os
import shutil
import tempfile

class TestMeaningfulLoopVariables(unittest.TestCase):
    def setUp(self):
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # 删除临时目录
        shutil.rmtree(self.test_dir)

    def run_check(self, directory):
        # 运行脚本并获取输出
        result = subprocess.run(
            ['python3', 'meaningful_loop_variables.py', directory],
            capture_output=True,
            text=True
        )
        return result.stdout, result.returncode

    def test_bad_naming(self):
        # 创建包含不合规变量的文件
        file_path = os.path.join(self.test_dir, 'bad.py')
        with open(file_path, 'w') as f:
            f.write("for i in range(10): pass\n")
            f.write("for x, y in [(1,2)]: pass\n")
        
        stdout, _ = self.run_check(self.test_dir)
        self.assertIn("使用了无意义的单字母变量 'i'", stdout)
        self.assertIn("使用了无意义的单字母变量 'x'", stdout)
        self.assertIn("使用了无意义的单字母变量 'y'", stdout)
        self.assertIn("总计发现 3 处不合规", stdout)

    def test_good_naming(self):
        # 创建包含合规变量的文件
        file_path = os.path.join(self.test_dir, 'good.py')
        with open(file_path, 'w') as f:
            f.write("for index in range(10): pass\n")
            f.write("for _, value in enumerate([1,2]): pass\n")
        
        stdout, _ = self.run_check(self.test_dir)
        self.assertIn("所有文件检查通过", stdout)

    def test_invalid_arg(self):
        # 测试无效参数
        _, returncode = self.run_check("non_existent_directory")
        self.assertEqual(returncode, 1)

    def test_skip_hidden_dir(self):
        # 创建隐藏目录及其中的不合规文件
        hidden_dir = os.path.join(self.test_dir, '.hidden')
        os.makedirs(hidden_dir)
        file_path = os.path.join(hidden_dir, 'bad.py')
        with open(file_path, 'w') as f:
            f.write("for i in range(10): pass\n")
        
        stdout, _ = self.run_check(self.test_dir)
        # 应该通过，因为隐藏目录被跳过
        self.assertIn("所有文件检查通过", stdout)

if __name__ == "__main__":
    unittest.main()
