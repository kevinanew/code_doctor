"""
# PRD (开发规范引用)
请在阅读本脚本具体功能前，务必先查看并遵守 `PRD_COMMON.md` 中的“通用开发规范”。

# 脚本具体 PRD: Python 镜像版本检查工具
## 1. 目标
确保项目中使用的 `python-driver:3.13` 镜像版本统一为官方指定的修复版本 `3.13.13-20260422`。
替换后需要复查,确保正确

## 2. 检查规则
- **检测范围**（限定范围）：
    1. 目标目录根下的 `Dockerfile`。
    2. 目标目录根下的 `.woodpecker/` 目录及其子目录中的所有文件。
- **触发条件**：
    - 匹配模式：镜像名包含 `python-driver:3.13`。
    - 不合规条件：版本号部分不是 `3.13.13-20260422`。
- **报告内容**：
    - 文件路径、行号、以及当前使用的不合规镜像版本。
- **AI Agent 动作指引**：
    - 使用 `replace` 工具将不合规的 `python-driver:3.13...` 替换为 `python-driver:3.13.13-20260422...`。

## 3. 命令行接口
- **用法**：`python Python镜像版本检查工具.py <target_directory>`
- **参数**：`<target_directory>` 是项目根目录路径。默认为当前目录 `.`。

## 4. 预期效果
- 仅检查目标目录根下的 `Dockerfile` 以及 `.woodpecker/` 目录。
- 打印出所有不符合规范的行及其修改建议。
- 如果发现不合规项，以退出码 `1` 退出；否则以 `0` 退出。
"""

import os
import re
import sys

# 正则表达式说明：
# 匹配 python-driver:3.13，后面可以跟可选所在的 .数字 或 -后缀
PYTHON_313_PATTERN = re.compile(r'python-driver:3\.13([0-9a-zA-Z.-]*)')
TARGET_IMAGE_NAME = "python-driver"
TARGET_VERSION = "3.13.13-20260422"

def check_file(file_path):
    """
    检查单个文件中的 Python 镜像版本。
    """
    if not os.path.exists(file_path):
        return 0

    violations = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for lineno, line in enumerate(f, 1):
                matches = PYTHON_313_PATTERN.finditer(line)
                for match in matches:
                    full_tag = match.group(0) # e.g. python-driver:3.13.1-slim
                    suffix = match.group(1)   # e.g. .1-slim

                    # 检查 suffix 是否以 .13-20260422 开头
                    if not suffix.startswith(".13-20260422"):
                        violations.append((lineno, full_tag, suffix))

        if violations:
            print(f"[{file_path}] 发现不合规的 Python 镜像版本：")
            for lineno, full_tag, suffix in violations:
                version_part_match = re.match(r'^(\.[0-9.]+)?(.*)', suffix)
                original_suffix_after_version = version_part_match.group(2) if version_part_match else ""

                suggested_tag = f"{TARGET_IMAGE_NAME}:{TARGET_VERSION}{original_suffix_after_version}"
                print(f"  第 {lineno} 行：使用了 '{full_tag}'。")
                print(f"  建议修改为：'{suggested_tag}'")
            print()
            return len(violations)

        return 0
    except (UnicodeDecodeError, PermissionError):
        # 忽略二进制文件或无权限文件
        return 0
    except Exception as e:
        print(f"无法读取文件 {file_path}: {e}")
        return 0

def main():
    target_dir = "."
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]

    if not os.path.isdir(target_dir):
        print(f"错误: '{target_dir}' 不是一个有效的目录。")
        sys.exit(1)

    total_violations = 0
    
    # 1. 检查根目录下的 Dockerfile
    root_dockerfile = os.path.join(target_dir, "Dockerfile")
    total_violations += check_file(root_dockerfile)
    
    # 2. 检查 .woodpecker 目录
    woodpecker_dir = os.path.join(target_dir, ".woodpecker")
    if os.path.isdir(woodpecker_dir):
        for root, _, files in os.walk(woodpecker_dir):
            for file in files:
                file_path = os.path.join(root, file)
                total_violations += check_file(file_path)

    if total_violations == 0:
        print("[镜像版本检查]: 成功。Dockerfile 和 .woodpecker/ 目录下的 Python 3.13 镜像均已对齐。")
        sys.exit(0)
    else:
        print(f"[镜像版本检查]: 发现 {total_violations} 处不合规的镜像版本。")
        print("\n### AI Agent 动作指引 ###")
        print("1. 请针对上述列出的文件和行号，核实是否需要更新。")
        print(f"2. 使用 `replace` 工具将不合规的 `python-driver:3.13...` 替换为 `python-driver:{TARGET_VERSION}`。替换后复查一下，确保正确")
        print("3. 确保保留原有的镜像后缀（如 -slim, -alpine）。")
        sys.exit(1)

if __name__ == "__main__":
    main()
