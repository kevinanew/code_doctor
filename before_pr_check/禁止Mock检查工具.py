#!/usr/bin/env python3

"""禁止 Mock 检查工具。

用法:
    python 禁止Mock检查工具.py [目录]

说明:
    - 检查当前分支相对于 master 分支新增加的代码中是否包含 mock。
    - 如果发现 mock 使用，脚本将报错并列出相关文件和行号。

PRD 摘要:
    1. 目标
       - 确保新代码中没有使用任何形式的 mock（如 unittest.mock, pytest-mock 等）。
       - 强制开发者通过更好的架构设计（如依赖注入、接口抽象）来实现测试，而不是依赖 mock。

    2. 运行约定
       - 接受一个参数：目标项目目录（默认为当前目录）。
       - 必须在 Git 仓库内执行。
       - 比较范围：`git diff master...HEAD`。
       - 发现 mock 时，输出具体位置并返回退出码 1。
       - 未发现时，返回退出码 0。

    3. 检查规则
       - 仅检查新增行（以 `+` 开头，排除 `+++`）。
       - 匹配关键字 `mock`（不区分大小写）。
       - 忽略隐藏目录（以 `.` 开头）中的文件。
       - 忽略测试脚本自身（如 `test_禁止Mock检查工具.py`）吗？通常工具脚本自身的测试可能也不应该用 mock，但这里我们严格执行：全项目禁用。
"""

import os
import subprocess
import sys
from typing import List, Tuple


class MockChecker:
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)

    def run_git_command(self, args: List[str]) -> str:
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Git 命令失败: {' '.join(e.cmd)}")
            print(f"错误输出: {e.stderr}")
            sys.exit(1)
        except FileNotFoundError:
            print("错误: 未找到 git 命令，请确保已安装 git。")
            sys.exit(1)

    def get_diff(self) -> str:
        # 尝试使用 master，如果失败尝试 main
        try:
            return self.run_git_command(["diff", "master...HEAD", "--unified=0"])
        except SystemExit:
            # 如果 master 不存在，尝试 main
            return self.run_git_command(["diff", "main...HEAD", "--unified=0"])

    def check_mock_usage(self) -> List[Tuple[str, str]]:
        diff_output = self.get_diff()
        violations = []
        current_file = ""

        for line in diff_output.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:]
                # 排除隐藏目录
                if any(part.startswith(".") for part in current_file.split(os.sep)):
                    current_file = ""
                continue

            if not current_file:
                continue

            if line.startswith("+") and not line.startswith("+++"):
                added_content = line[1:].strip()
                if "mock" in added_content.lower():
                    violations.append((current_file, added_content))

        return violations

    def run(self):
        print(f"正在检查目录: {self.root_dir}")
        violations = self.check_mock_usage()

        if violations:
            print("\n❌ 发现禁止使用的 mock 代码:")
            for file_path, content in violations:
                print(f"  文件: {file_path}")
                print(f"  内容: {content}")
                print("-" * 20)
            print("\n错误: 绝对不能使用 mock！请重构代码以提高可测性。")
            sys.exit(1)
        else:
            print("\n✅ 未发现 mock 使用，检查通过。")
            sys.exit(0)


if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    checker = MockChecker(target_dir)
    checker.run()
