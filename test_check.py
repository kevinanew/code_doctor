#!/usr/bin/env python3
import unittest
import subprocess
import os
import sys
import shutil
import tempfile


class TestCheck(unittest.TestCase):
    def setUp(self):
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        # 初始化 git 仓库
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True)
        # 配置 git 用户信息以便 commit
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=self.test_dir
        )
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir)
        # 创建 .gitignore 忽略 check.log
        with open(os.path.join(self.test_dir, ".gitignore"), "w") as f:
            f.write("check.log\n")

    def tearDown(self):
        # 删除临时目录
        shutil.rmtree(self.test_dir)

    def test_run_check_flow(self):
        """
        测试 check.py 的完整流程：按顺序运行 ALL_SCRIPTS、生成日志。
        """
        # 1. 准备环境：复制 check.py 并创建 ALL_SCRIPTS 中的脚本
        script_dir = os.path.dirname(os.path.abspath(__file__))
        shutil.copy(os.path.join(script_dir, "check.py"), self.test_dir)

        # 动态导入 ALL_SCRIPTS
        sys.path.insert(0, self.test_dir)
        import check

        all_scripts = check.ALL_SCRIPTS
        sys.path.pop(0)

        for rel_path in all_scripts:
            full_path = os.path.join(self.test_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            script_name = os.path.basename(rel_path)
            with open(full_path, "w") as f:
                f.write(f"import sys\nprint('Running {script_name}')\nsys.exit(0)\n")

        # 提交所有内容以确保 git 状态干净
        subprocess.run(["git", "add", "."], cwd=self.test_dir, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=self.test_dir,
            capture_output=True,
        )

        # 2. 运行 check.py
        result = subprocess.run(
            ["python3", "check.py", "."],
            capture_output=True,
            text=True,
            cwd=self.test_dir,
        )

        # 检查是否成功运行
        self.assertEqual(
            result.returncode, 0, f"check.py 运行失败: {result.stdout}\n{result.stderr}"
        )

        # 3. 验证 check.log
        log_path = os.path.join(self.test_dir, "check.log")
        self.assertTrue(os.path.exists(log_path), "check.log 未创建")

        with open(log_path, "r", encoding="utf-8") as f:
            log_content = f.read()

        # 验证开始标记
        self.assertIn("=== 开始全量检查，目标目录:", log_content)

        # 验证运行顺序
        last_index = -1
        for rel_path in all_scripts:
            script_name = os.path.basename(rel_path)
            search_str = f"正在运行 {script_name}..."
            self.assertIn(search_str, log_content)
            current_index = log_content.find(search_str)
            self.assertTrue(
                current_index > last_index, f"脚本 {script_name} 运行顺序错误"
            )
            last_index = current_index

        # 验证分隔符
        self.assertIn("-" * 40, log_content)

    def test_git_modification_interrupt(self):
        """
        测试当脚本修改了文件时，check.py 是否能检测到并中断。
        """
        shutil.copy(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "check.py"),
            self.test_dir,
        )

        # 创建一个会修改文件的脚本
        modifier_script = "开发环境删除工具.py"  # 它是优先级最高的
        with open(os.path.join(self.test_dir, modifier_script), "w") as f:
            f.write("import os\n")
            f.write("with open('changed.txt', 'w') as f: f.write('changed')\n")
            f.write("print('Modified a file')\n")

        # 创建另一个脚本，不应该被运行
        second_script = "配置文件归位工具.py"
        with open(os.path.join(self.test_dir, second_script), "w") as f:
            f.write("print('Should not run')\n")

        # 提交初始状态
        subprocess.run(["git", "add", "."], cwd=self.test_dir, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=self.test_dir,
            capture_output=True,
        )

        # 运行 check.py
        result = subprocess.run(
            ["python3", "check.py", "."],
            capture_output=True,
            text=True,
            cwd=self.test_dir,
        )

        # 应该返回 1 (中断)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[警告]: 检测到本地文件已被修改或自动修复。", result.stdout)
        self.assertIn("Modified a file", result.stdout)
        self.assertNotIn("Should not run", result.stdout)

    def test_preexisting_untracked_file_does_not_interrupt(self):
        """
        测试仓库里预先存在的未跟踪文件不会误触发中断。
        """
        shutil.copy(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "check.py"),
            self.test_dir,
        )

        with open(os.path.join(self.test_dir, "preexisting.txt"), "w") as f:
            f.write("already here\n")

        first_script = "开发环境删除工具.py"
        with open(os.path.join(self.test_dir, first_script), "w") as f:
            f.write("print('No change')\n")

        second_script = "配置文件归位工具.py"
        with open(os.path.join(self.test_dir, second_script), "w") as f:
            f.write("print('Still no change')\n")

        subprocess.run(["git", "add", "."], cwd=self.test_dir, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=self.test_dir,
            capture_output=True,
        )

        # 在提交后创建一个未跟踪文件，模拟仓库本来就处于 dirty 状态
        with open(os.path.join(self.test_dir, "preexisting.txt"), "w") as f:
            f.write("already here\n")

        result = subprocess.run(
            ["python3", "check.py", "."],
            capture_output=True,
            text=True,
            cwd=self.test_dir,
        )

        self.assertEqual(
            result.returncode, 0, f"check.py 运行失败: {result.stdout}\n{result.stderr}"
        )
        self.assertIn("正在运行 开发环境删除工具.py...", result.stdout)
        self.assertIn("正在运行 配置文件归位工具.py...", result.stdout)
        self.assertNotIn("[警告]: 检测到本地文件已被修改或自动修复。", result.stdout)


if __name__ == "__main__":
    unittest.main()
