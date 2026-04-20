"""
# PRD: 开发环境（Development）删除工具

## 1. 目标
在目标项目中自动识别是否存在 Development 环境配置。
一旦发现该环境存在，则输出一段可直接交给 AI Agent 的“删除 Development 环境”执行提示词，用于驱动后续代码改造。

## 2. 检查规则
- **检查范围**：Makefile、docker/docker-compose.yml、src/config.py、src/sdk/sdk_client.py
- **触发条件**：检查范围文件中存在 `development`。
- **报告内容**：文件路径、行号

## 3. 命令行接口
- **用法**：`python 开发环境删除提示词生成工具.py <target_directory>`
- **参数**：`<target_directory>` 是需要检查的目录路径。
- **默认行为**：如果未传入参数，则默认使用当前工作目录作为目标目录。

## 4. 预期效果
- 检查目标文件中是否存在 development 环境配置
- 打印出有 development 的行及删除建议。
- 如果没有发现 development 环境配置，则给出简单的“检查通过”提示。

## . 语言要求
- **最后，请 AI Agent 使用中文回答。**
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence


@dataclass(frozen=True)
class 命中项:
    相对路径: str
    行号: int
    行内容: str


def _读取文本(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _扫描文件(root_dir: Path, rel_path: str, keyword: str) -> List[命中项]:
    path = (root_dir / rel_path).resolve()
    if not path.is_file():
        return []

    try:
        content = _读取文本(path)
    except OSError:
        return []

    results: List[命中项] = []
    for idx, line in enumerate(content.splitlines(), start=1):
        if keyword in line:
            preview = line.rstrip("\n")
            if len(preview) > 240:
                preview = preview[:240] + "…"
            results.append(命中项(相对路径=rel_path, 行号=idx, 行内容=preview))
    return results


def _格式化命中(matches: Sequence[命中项], max_matches: int = 80) -> str:
    if not matches:
        return "（未发现命中）"
    shown = matches[: max_matches]
    lines = [f"- {m.相对路径}:{m.行号} | {m.行内容}" for m in shown]
    if len(matches) > len(shown):
        lines.append(f"- ……（共 {len(matches)} 处，仅展示前 {len(shown)} 处）")
    return "\n".join(lines)


def _构建提示词(target_dir: Path, matches: Sequence[命中项]) -> str:
    hit_section = _格式化命中(matches)
    return (
        f"目标项目目录：{target_dir}\n"
        "目标：删除 Development（development）环境配置，确保项目不再出现 `development` 相关内容。\n\n"
        "执行要求：\n"
        "逐个处理下方命中位置，删除或使用 testing 替换掉 `development`。\n\n"
        "命中位置：\n"
        f"{hit_section}\n\n"
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

    files_to_check = [
        "Makefile",
        "docker/docker-compose.yml",
        "src/config.py",
        "src/sdk/sdk_client.py",
    ]

    all_matches: List[命中项] = []
    for rel in files_to_check:
        all_matches.extend(_扫描文件(target_dir, rel, keyword="development"))

    if not all_matches:
        print("检查通过：未发现 Development（development）环境配置。")
        return

    print(_构建提示词(target_dir, all_matches))
    sys.exit(1)


if __name__ == "__main__":
    main()
