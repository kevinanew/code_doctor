#!/usr/bin/env python3

"""
# PRD (开发规范引用)
请在阅读本脚本具体功能前，务必先查看并遵守 `PRD_COMMON.md` 中的“通用开发规范”。

# 脚本具体 PRD: Nested For Loop Check
## 1. 目标
防止过度嵌套的循环逻辑，降低代码复杂度，提高可读性和可维护性。

## 2. 检查规则
- **检测对象**：所有 Python 脚本文件（.py）。
- **触发条件**：在 `for` 或 `async for` 循环中，如果嵌套深度超过 2 层（即出现第 3 层循环），则视为不合规。
- **报告内容**：文件路径、行号、以及当前嵌套深度。

## 3. PR 规范
- **中文 PR**：创建 Pull Request 时，**PR 标题和描述必须使用中文**。

## 4. 命令行接口
- **用法**：`python 嵌套循环检查.py <target_directory>`
- **参数**：`<target_directory>` 是需要递归检查的目录路径。如果不提供，则默认检查当前目录。

## 5. 预期效果
- 扫描目录下的所有 .py 文件。
- 打印出所有不符合规范的行及其嵌套深度。
- 如果没有发现问题，则以 0 退出；发现问题则以 1 退出。
"""

import ast
import os
import sys


class NestedLoopVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []
        self.current_depth = 0

    def visit_For(self, node):
        self.current_depth += 1
        if self.current_depth > 2:
            self.violations.append((node.lineno, self.current_depth))
        self.generic_visit(node)
        self.current_depth -= 1

    def visit_AsyncFor(self, node):
        self.current_depth += 1
        if self.current_depth > 2:
            self.violations.append((node.lineno, self.current_depth))
        self.generic_visit(node)
        self.current_depth -= 1


def check_file(file_path):
    """
    检查单个文件中的嵌套循环。
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)
        visitor = NestedLoopVisitor()
        visitor.visit(tree)

        if visitor.violations:
            print(f"[{file_path}] 发现过度嵌套的循环：")
            for lineno, depth in visitor.violations:
                print(
                    f"  第 {lineno} 行：循环嵌套深度为 {depth}。建议将内层逻辑提取为函数或重构逻辑。"
                )
            print()
            return len(visitor.violations)
        return 0

    except Exception as e:
        print(f"无法解析文件 {file_path}: {e}")
        return 0


def main():
    target_dir = "."
    if len(sys.argv) == 2:
        target_dir = sys.argv[1]
    elif len(sys.argv) > 2:
        print("用法: python 嵌套循环检查.py <target_directory>")
        sys.exit(1)

    if not os.path.isdir(target_dir):
        print(f"错误: '{target_dir}' 不是一个有效的目录。")
        sys.exit(1)

    total_violations = 0
    for root, dirs, files in os.walk(target_dir):
        # 排除以 . 开头的隐藏目录
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                # 排除自身和测试文件
                if os.path.abspath(file_path) == os.path.abspath(__file__):
                    continue
                total_violations += check_file(file_path)

    if total_violations == 0:
        print("所有文件检查通过，未发现过度嵌套的循环。")
        sys.exit(0)
    else:
        print(f"总计发现 {total_violations} 处不合规。")
        print("\n[AI Agent 动作指引]:")
        print(
            "1. **重构代码**：请根据上述提示将过度嵌套的循环重构，建议将内层逻辑提取为独立函数或简化逻辑。"
        )
        print("2. **PR 规范**：创建 Pull Request 时，**PR 标题和描述必须使用中文**。")
        print("\n最后，请使用中文回答。")
        sys.exit(1)


if __name__ == "__main__":
    main()
