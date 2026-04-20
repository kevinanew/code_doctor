"""
# PRD (开发规范引用)
请在阅读本脚本具体功能前，务必先查看并遵守 `PRD_COMMON.md` 中的“通用开发规范”。

# 脚本具体 PRD: 开发环境（Development）删除工具

## 1. 目标
在目标项目中自动识别是否存在 Development 环境配置（仅以 `src/configs.py` 中出现 `class Development` 为准）。
一旦发现该环境存在，则输出一段可直接交给 AI Agent 的“删除 Development 环境”执行提示词，用于驱动后续代码改造。

## 2. 检查规则
- **触发条件**：`<target_directory>/src/configs.py` 中存在 `class Development`。
- **扫描范围**：仅检查 `src/configs.py` 文件。
- **排除范围**：跳过所有以点（.）开头的隐藏目录。

## 3. 命令行接口
- **用法**：`python 开发环境删除工具.py <target_directory>`
- **参数**：`<target_directory>` 是需要检查的目录路径。
- **默认行为**：如果未传入参数，则默认使用当前工作目录作为目标目录。

## 4. 预期效果
- 若未检测到 `class Development`：输出“检查通过”的提示，并以 0 退出。
- 若检测到 `class Development`：输出“Development 环境删除任务提示词”，并以 1 退出。
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


CLASS_DEVELOPMENT_RE = re.compile(r"^\s*class\s+Development\b", re.MULTILINE)


@dataclass(frozen=True)
class Match:
    relative_path: str
    line_no: int
    line: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _build_prompt(target_dir: Path, configs_rel_path: str, line_no: int) -> str:
    return (
        "你是资深 Python 工程师。全程使用中文沟通。\n\n"
        f"目标项目目录：{target_dir}\n"
        "目标：删除 Development 环境配置。\n\n"
        "执行要求：\n"
        f"1) 修改 {configs_rel_path}：删除 `class Development` 及其相关代码（约第 {line_no} 行）。\n"
        "2) 确保项目中不再有对 `Development` 类的引用（若有，请适配为 testing 环境）。\n\n"
        "最后，请使用中文回答。"
    )


def main() -> None:
    if len(sys.argv) not in (1, 2):
        print("用法: python 开发环境删除工具.py <target_directory>")
        sys.exit(1)

    target_dir = Path(sys.argv[1] if len(sys.argv) == 2 else ".").resolve()
    if not target_dir.is_dir():
        print(f"错误: '{target_dir}' 不是一个有效的目录。")
        sys.exit(1)

    # 根据 PRD 仅检查 src/configs.py
    configs_path = target_dir / "src" / "configs.py"
    if not configs_path.is_file():
        # 如果文件不存在，视作检查通过（无此配置）
        print(f"检查通过：未发现配置文件 {configs_path.relative_to(target_dir) if configs_path.is_relative_to(target_dir) else configs_path}。")
        return

    configs_text = _read_text(configs_path)
    match = CLASS_DEVELOPMENT_RE.search(configs_text)
    
    if not match:
        print("检查通过：未检测到 `class Development`，无需删除 Development 环境。")
        return

    # 获取行号
    line_no = configs_text.count("\n", 0, match.start()) + 1
    rel_path = str(configs_path.relative_to(target_dir))

    print(_build_prompt(target_dir, rel_path, line_no))
    sys.exit(1)


if __name__ == "__main__":
    main()
