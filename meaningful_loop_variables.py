"""
# PRD: Meaningful Loop Variables Check

## 1. 目标
提高代码的可读性和可维护性，通过强制要求 `for` 循环中的迭代变量具有明确的业务含义，避免使用无意义的单字母变量（如 `i`, `j`, `x` 等）。

## 2. 检查规则
- **检测对象**：所有 Python 脚本文件（.py）。
- **触发条件**：在 `for` 循环语句中，如果定义的迭代变量（target）是单个字母（A-Z, a-z），则视为不合规。
- **例外情况**：下划线 `_` 常用于表示忽略该变量，不属于报错范围。
- **报告内容**：文件路径、行号、以及具体的修改建议。

## 3. 命令行接口
- **用法**：`python meaningful_loop_variables.py <target_directory>`
- **参数**：`<target_directory>` 是需要递归检查的目录路径。

## 4. 预期效果
- 扫描目录下的所有 .py 文件。
- 打印出所有不符合规范的行及其建议。
- 如果没有发现问题，则静默退出或给出简单的“检查通过”提示。
"""

import ast
import os
import sys

def check_file(file_path):
    """
    检查单个文件中的 for 循环变量。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                # 检查 for 循环的目标变量
                if isinstance(node.target, ast.Name):
                    var_name = node.target.id
                    if len(var_name) == 1 and var_name != '_':
                        violations.append((node.lineno, var_name))
                elif isinstance(node.target, ast.Tuple):
                    # 如果是 for i, j in ... 的情况
                    for elt in node.target.elts:
                        if isinstance(elt, ast.Name):
                            var_name = elt.id
                            if len(var_name) == 1 and var_name != '_':
                                violations.append((node.lineno, var_name))

        if violations:
            print(f"[{file_path}] 发现不合规的循环变量：")
            for lineno, var_name in violations:
                print(f"  第 {lineno} 行：使用了无意义的单字母变量 '{var_name}'。建议更改为更具描述性的名称。")
            print()
            return len(violations)
        return 0

    except Exception as e:
        print(f"无法解析文件 {file_path}: {e}")
        return 0

def main():
    if len(sys.argv) != 2:
        print("用法: python meaningful_loop_variables.py <target_directory>")
        sys.exit(1)

    target_dir = sys.argv[1]
    if not os.path.isdir(target_dir):
        print(f"错误: '{target_dir}' 不是一个有效的目录。")
        sys.exit(1)

    total_violations = 0
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                total_violations += check_file(file_path)

    if total_violations == 0:
        print("所有文件检查通过，未发现无意义的循环变量。")
    else:
        print(f"总计发现 {total_violations} 处不合规。")

if __name__ == "__main__":
    main()
