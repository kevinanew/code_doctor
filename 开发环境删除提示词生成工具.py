"""
# PRD: 开发环境（Development）删除提示词生成工具

## 1. 目标
在目标项目中自动识别是否存在 Development 环境配置（以 `src/configs.py` 中出现 `class Development` 为准）。
一旦发现该环境存在，则输出一段可直接交给 AI Agent 的“删除 Development 环境”执行提示词，用于驱动后续代码改造。

## 2. 检查规则
- **触发条件**：`<target_directory>/src/configs.py` 中存在 `class Development`。
- **重点文件**（优先列出引用位置）：
  - `src/configs.py`
  - `docker/docker-compose.yml`
  - `Makefile`
- **扫描范围**：递归扫描目标目录下的常见文本文件，定位 `Development` / `development` / `STAGE` 相关引用位置。
- **排除范围**：跳过所有以点（.）开头的隐藏目录（如 `.git`, `.venv` 等）。

## 3. 命令行接口
- **用法**：`python 开发环境删除提示词生成工具.py <target_directory>`
- **参数**：`<target_directory>` 是需要检查的目录路径。
- **默认行为**：如果未传入参数，则默认使用当前工作目录作为目标目录。

## 4. 预期效果
- 若未检测到 `class Development`：输出“检查通过”的提示，并以 0 退出。
- 若检测到 `class Development`：输出“Development 环境删除任务提示词”，并以 1 退出（用于在全量检查中触发失败）。

## 5. 语言要求
- **最后，请 AI Agent 使用中文回答。**
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


CLASS_DEVELOPMENT_RE = re.compile(r"^\s*class\s+Development\b", re.MULTILINE)


@dataclass(frozen=True)
class Match:
    relative_path: str
    line_no: int
    line: str


def _is_hidden_dir(name: str) -> bool:
    return name.startswith(".")


def _is_probably_text_file(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz", ".tar", ".xz", ".7z"}:
        return False
    try:
        if path.stat().st_size > 1024 * 1024:
            return False
    except FileNotFoundError:
        return False
    return True


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _iter_files(root_dir: Path) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if not _is_hidden_dir(d)]
        for filename in files:
            if filename.startswith("."):
                continue
            yield Path(current_root) / filename


def _grep_file(path: Path, root_dir: Path, patterns: Sequence[re.Pattern[str]]) -> List[Match]:
    if not path.is_file() or not _is_probably_text_file(path):
        return []
    try:
        content = _read_text(path)
    except OSError:
        return []

    rel = str(path.resolve().relative_to(root_dir.resolve()))
    results: List[Match] = []
    for idx, line in enumerate(content.splitlines(), start=1):
        for pat in patterns:
            if pat.search(line):
                preview = line.rstrip("\n")
                if len(preview) > 240:
                    preview = preview[:240] + "…"
                results.append(Match(relative_path=rel, line_no=idx, line=preview))
                break
    return results


def _format_matches(matches: Sequence[Match], max_matches: int = 40) -> str:
    if not matches:
        return "（未发现引用）"
    shown = matches[: max_matches]
    lines = [f"- {m.relative_path}:{m.line_no} | {m.line}" for m in shown]
    if len(matches) > len(shown):
        lines.append(f"- ……（共 {len(matches)} 处，仅展示前 {len(shown)} 处）")
    return "\n".join(lines)


def _build_prompt(target_dir: Path, key_matches: Sequence[Match], all_matches: Sequence[Match]) -> str:
    key_section = _format_matches(key_matches, max_matches=60)
    all_section = _format_matches(all_matches, max_matches=60)

    return (
        "你是资深 Python 工程师。全程使用中文沟通。\n\n"
        f"目标项目目录：{target_dir}\n"
        "目标：删除 Development 环境，并将所有原本使用 Development 环境的地方改为 testing 环境。\n\n"
        "关键原则：彻底删除。不要保留任何 development/Development 相关配置、分支或文案。\n\n"
        "执行要求（务必逐条完成）：\n"
        "1) 修改 src/configs.py：删除 `class Development`。\n"
        "2) 全项目删除所有 `development`/`Development` 的使用：包括环境变量值、配置选择逻辑、条件分支、导入、注释与文档中的指引（如需保留历史说明也必须改为 testing）。\n"
        "3) 检查并更新重点文件：docker/docker-compose.yml、Makefile，确保不再设置或依赖 Development，而是使用 testing。\n"
        "4) 全项目搜索并修复残留引用（关键字：Development、development、STAGE）。\n"
        "5) 最小验证：至少跑一次单元测试或启动检查。\n\n"
        "建议步骤：\n"
        "- 先全项目定位引用：`rg -n 'Development|development|\\bSTAGE\\b' .`\n"
        "- 修改后再次搜索：确保 `Development` 与 `development` 均已清零；若仍存在，继续修复直到清零。\n\n"
        "重点文件命中位置（优先处理）：\n"
        f"{key_section}\n\n"
        "全项目命中位置（辅助排查）：\n"
        f"{all_section}\n"
        "\n最后，请使用中文回答。"
    )


def main() -> None:
    if len(sys.argv) not in (1, 2):
        print("用法: python 开发环境删除提示词生成工具.py <target_directory>")
        sys.exit(1)

    target_dir = Path(sys.argv[1] if len(sys.argv) == 2 else ".").resolve()
    if not target_dir.is_dir():
        print(f"错误: '{target_dir}' 不是一个有效的目录。")
        sys.exit(1)

    configs_path = target_dir / "src" / "configs.py"
    if not configs_path.is_file():
        print(f"错误: 未找到重点文件: {configs_path}")
        sys.exit(1)

    configs_text = _read_text(configs_path)
    if not CLASS_DEVELOPMENT_RE.search(configs_text):
        print("检查通过：未检测到 `class Development`，无需删除 Development 环境。")
        return

    key_files = [
        target_dir / "src" / "configs.py",
        target_dir / "docker" / "docker-compose.yml",
        target_dir / "Makefile",
    ]

    patterns = [
        re.compile(r"\bDevelopment\b"),
        re.compile(r"\bdevelopment\b"),
        re.compile(r"\bSTAGE\b"),
    ]

    key_matches: List[Match] = []
    for f in key_files:
        key_matches.extend(_grep_file(f, target_dir, patterns))

    all_matches: List[Match] = []
    for p in _iter_files(target_dir):
        if p in key_files:
            continue
        all_matches.extend(_grep_file(p, target_dir, patterns))

    print(_build_prompt(target_dir, key_matches=key_matches, all_matches=all_matches))
    sys.exit(1)


if __name__ == "__main__":
    main()

