"""
# PRD (开发规范引用)
请在阅读本脚本具体功能前，务必先查看并遵守 `PRD_COMMON.md` 中的“通用开发规范”。

# 脚本具体 PRD: external-SDK-Upgrade-Checker

## 1. 产品概述

### 1.1 产品定位
这是一个给 Python 项目维护者和 AI agent 使用的 `CLI` 检查工具，用来判断当前项目 `src/sdk` 下的**本项目 SDK 之外的 SDK**是否已经和 `/home/coder/github/kevinanew/api_sdk/python` 中的最新 SDK 对齐。

工具只做检查和输出，不直接修改代码。

### 1.2 核心目标
- 自动找出当前项目里需要检查的 SDK
- 拉取最新的 `api_sdk` 版本作为对照
- 通过主文件对比判断 SDK 是否已升级
- 生成给 AI agent 使用的 Markdown 提示词
- 为未升级的 SDK 生成可直接交给 AI agent 的升级提示词
- 兼容 `check.py` 的判定方式：子脚本是否通过只看退出码，`0` 代表通过，`1` 代表失败

### 1.3 产品形态
- **形态**：Python CLI 脚本
- **输出**：仅输出给 AI agent 的 Markdown 提示词
- **用途**：本地执行、CI 执行、AI agent 读取

### 1.4 使用方法
```bash
python code_doctor/外部SDK升级检查器.py <项目名>
```

- `<项目名>` 可选
- 如果不指定项目名，脚本默认在当前命令执行目录下进行检查
- 如果指定项目名，脚本应以该项目名作为识别和检查的基准

---

## 2. 规则定义

- **本项目 SDK**：项目名与 sdk 名系统一致的那个 SDK，直接固定识别，不参与升级检查。
- **非本项目 SDK**：当前项目 `src/sdk` 下除本项目 SDK 之外的其他 SDK。
- **最新版本来源**：`/home/coder/github/kevinanew/api_sdk/python`
- **参考仓库更新规则**：检查前必须先更新 `api_sdk` 的 `master` 分支，且必须按以下顺序执行：
  1. `cd /home/coder/github/kevinanew/api_sdk`
  2. `git fetch origin`
  3. `git checkout master`
  4. `git reset --hard origin/master`
  如果更新失败，直接退出并提示“更新失败，请重试”。
- **主文件规则**：优先使用 `目录名同名 .py`，找不到则回退到 `__init__.py`。
- **升级判定规则**：当前项目主文件与最新 SDK 主文件无差异，则判定为“已升级”。
- **处理上限**：一次脚本运行最多只处理 3 个未升级 SDK；超过 3 个时，仅选择前 3 个进入提示词生成流程，其余只标注数量，不进入本轮处理。
- **SDK 补齐规则**：若当前项目某个 SDK 中没有 `sdk_client.py` 与 `test_client`，则从参考项目中复制到当前项目对应 SDK 目录下。
- **对齐规则**：需要对齐当前项目与参考仓库中对应 SDK 的所有文件。
- **修改边界**：不要修改本项目中与上述 SDK 无关的内容。
- **结构一致性**：更新后保持文件结构与命名一致。
- **扫描排除规则**：扫描时排除 `__pycache__`，以及所有开头是 `.` 的文件和文件夹。
- **输出方式**：仅输出到 stdout，且最终只输出给 agent 的提示词。
- **无法判断处理规则**：无法判断的 SDK 不进入本轮处理，不作为升级目标；但其名称需要在最终输出中单独列出。
- **通过判定规则**：如果本次没有需要升级的 SDK，脚本必须输出“无需要升级的 SDK”，并以 `0` 退出，确保 `check.py` 判定为通过。

---

## 3. AI agent 提示词生成

### 3.1 提示词要求
- 明确列出 SDK 名称
- 明确说明当前项目根目录与参考仓库的 SDK 目录，且参考仓库的 `sdk_client.py` 位于该 SDK 目录下
- 明确要求对齐主文件
- 明确要求补齐 `sdk_client.py` 与 `test_client`，如果当前项目缺失则从参考项目复制
- 明确要求对齐当前项目与参考仓库中对应 SDK 的所有文件
- 明确要求不要修改本项目不相关内容
- 明确要求更新后保持文件结构一致
- 明确要求不要修改本项目中与上述 SDK 无关的内容
- 明确要求在补齐 SDK 本体后，检查项目中所有调用这些 SDK 的地方，并将调用改为最新方式
- 明确要求重点检查 SDK 更新后是否需要实例化，以及调用方式是否发生变化
- 提示词本身应成为脚本最终输出的唯一内容
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


DEFAULT_API_SDK_REPO = Path("/home/coder/github/kevinanew/api_sdk")
SKIP_UPDATE_ENV = "CODE_DOCTOR_SKIP_API_SDK_UPDATE"
API_SDK_REPO_ENV = "CODE_DOCTOR_API_SDK_REPO_ROOT"
MAX_UNUPGRADED = 3


@dataclass(frozen=True)
class SDKState:
    名称: str
    当前目录: Path
    参考目录: Path
    当前主文件: Optional[Path]
    参考主文件: Optional[Path]
    判定: str
    缺失文件: List[str]
    原因: Optional[str] = None


def _api_sdk_repo_root() -> Path:
    raw = os.getenv(API_SDK_REPO_ENV)
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_API_SDK_REPO


def _api_sdk_python_root() -> Path:
    return _api_sdk_repo_root() / "python"


def _should_skip_update() -> bool:
    return os.getenv(SKIP_UPDATE_ENV, "").strip() == "1"


def _run_command(command: List[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)


def _update_reference_repo() -> tuple[bool, str]:
    if _should_skip_update():
        return True, ""

    repo_root = _api_sdk_repo_root()
    if not repo_root.is_dir():
        return False, f"参考仓库目录不存在: {repo_root}"

    commands = [
        ["git", "fetch", "origin"],
        ["git", "checkout", "master"],
        ["git", "reset", "--hard", "origin/master"],
    ]
    for command in commands:
        result = _run_command(command, repo_root)
        if result.returncode != 0:
            detail = (result.stdout or "") + (result.stderr or "")
            detail = detail.strip()
            if detail:
                return False, detail
            return False, "git 命令执行失败"
    return True, ""


def _resolve_target_dir(argv: List[str]) -> Path:
    if len(argv) not in (1, 2):
        raise ValueError("用法: python 外部SDK升级检查器.py <target_directory>")
    target_dir = Path(argv[1] if len(argv) == 2 else ".").resolve()
    if not target_dir.is_dir():
        raise NotADirectoryError(f"'{target_dir}' 不是一个有效的目录。")
    return target_dir


def _iter_sdk_dirs(sdk_root: Path, self_sdk_name: str) -> List[Path]:
    if not sdk_root.is_dir():
        return []
    items = []
    for child in sorted(sdk_root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name == "__pycache__":
            continue
        if child.name == self_sdk_name:
            continue
        items.append(child)
    return items


def _locate_main_file(sdk_dir: Path) -> Optional[Path]:
    primary = sdk_dir / f"{sdk_dir.name}.py"
    if primary.is_file():
        return primary
    init_file = sdk_dir / "__init__.py"
    if init_file.is_file():
        return init_file
    return None


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _compare_files(left: Path, right: Path) -> Optional[bool]:
    left_content = _read_text(left)
    right_content = _read_text(right)
    if left_content is None or right_content is None:
        return None
    return left_content == right_content


def _detect_missing_files(current_dir: Path, reference_dir: Path) -> List[str]:
    missing: List[str] = []
    candidates = [
        "sdk_client.py",
        "test_client.py",
        "test_client",
    ]
    for name in candidates:
        ref_path = reference_dir / name
        cur_path = current_dir / name
        if ref_path.exists() and not cur_path.exists():
            missing.append(name)
    return missing


def _build_state(sdk_dir: Path, api_root: Path) -> SDKState:
    ref_dir = api_root / sdk_dir.name
    cur_main = _locate_main_file(sdk_dir)
    ref_main = _locate_main_file(ref_dir) if ref_dir.is_dir() else None

    if not ref_dir.is_dir():
        return SDKState(
            名称=sdk_dir.name,
            当前目录=sdk_dir,
            参考目录=ref_dir,
            当前主文件=cur_main,
            参考主文件=ref_main,
            判定="无法判断",
            缺失文件=[],
            原因="参考仓库中不存在同名 SDK 目录",
        )

    missing = _detect_missing_files(sdk_dir, ref_dir)
    if cur_main is None or ref_main is None:
        reason = []
        if cur_main is None:
            reason.append("当前项目主文件不存在")
        if ref_main is None:
            reason.append("参考仓库主文件不存在")
        return SDKState(
            名称=sdk_dir.name,
            当前目录=sdk_dir,
            参考目录=ref_dir,
            当前主文件=cur_main,
            参考主文件=ref_main,
            判定="无法判断",
            缺失文件=missing,
            原因="；".join(reason),
        )

    compared = _compare_files(cur_main, ref_main)
    if compared is None:
        return SDKState(
            名称=sdk_dir.name,
            当前目录=sdk_dir,
            参考目录=ref_dir,
            当前主文件=cur_main,
            参考主文件=ref_main,
            判定="无法判断",
            缺失文件=missing,
            原因="主文件读取失败或比较失败",
        )

    if compared and missing:
        return SDKState(
            名称=sdk_dir.name,
            当前目录=sdk_dir,
            参考目录=ref_dir,
            当前主文件=cur_main,
            参考主文件=ref_main,
            判定="未升级",
            缺失文件=missing,
            原因="当前项目缺少参考仓库已有文件，需要补齐",
        )

    return SDKState(
        名称=sdk_dir.name,
        当前目录=sdk_dir,
        参考目录=ref_dir,
        当前主文件=cur_main,
        参考主文件=ref_main,
        判定="已升级" if compared else "未升级",
        缺失文件=missing,
        原因=None,
    )


def _format_path(path: Optional[Path]) -> str:
    return f"`{path}`" if path is not None else "`未找到`"


def _format_sdk_line(state: SDKState) -> str:
    lines = [
        f"- `{state.名称}`",
        f"  - 当前目录: `{state.当前目录}`",
        f"  - 参考目录: `{state.参考目录}`",
        f"  - 当前主文件: {_format_path(state.当前主文件)}",
        f"  - 参考主文件: {_format_path(state.参考主文件)}",
        f"  - 判定: {state.判定}",
    ]
    if state.缺失文件:
        lines.append(f"  - 需补齐文件: {', '.join(f'`{name}`' for name in state.缺失文件)}")
    if state.原因:
        lines.append(f"  - 原因: {state.原因}")
    return "\n".join(lines)


def _format_prompt(
    target_dir: Path,
    api_root: Path,
    states: List[SDKState],
    unable_states: List[SDKState],
) -> str:
    upgrade_targets = [state for state in states if state.判定 == "未升级"]
    selected_targets = upgrade_targets[:MAX_UNUPGRADED]
    overflow = len(upgrade_targets) - len(selected_targets)

    if not selected_targets:
        parts = ["无需要升级的 SDK"]
        if unable_states:
            parts.append("")
            parts.append("## 无法判断的 SDK")
            for state in unable_states:
                parts.append(f"- `{state.名称}`")
                if state.原因:
                    parts.append(f"  - 原因: {state.原因}")
                if state.缺失文件:
                    parts.append(f"  - 需补齐文件: {', '.join(f'`{name}`' for name in state.缺失文件)}")
        return "\n".join(parts)

    prompt_lines = [
        "# 外部 SDK 升级任务",
        "",
        "## 目标",
        "请对下列未升级的外部 SDK 进行对齐、补齐和调用方式更新。",
        "",
        "## 运行上下文",
        f"- 当前项目根目录: `{target_dir}`",
        f"- 参考仓库 SDK 根目录: `{api_root}`",
        "- 参考仓库中的 `sdk_client.py` 位于对应 SDK 目录下。",
        "",
        "## 需要处理的 SDK",
    ]
    for state in selected_targets:
        prompt_lines.append(_format_sdk_line(state))

    if overflow > 0:
        prompt_lines.extend(
            [
                "",
                f"## 其余未升级 SDK",
                f"- 还有 {overflow} 个未升级 SDK 本轮不处理，只统计数量。",
            ]
        )

    if unable_states:
        prompt_lines.extend(["", "## 无法判断的 SDK"])
        for state in unable_states:
            prompt_lines.append(f"- `{state.名称}`")
            if state.原因:
                prompt_lines.append(f"  - 原因: {state.原因}")
            if state.缺失文件:
                prompt_lines.append(f"  - 需补齐文件: {', '.join(f'`{name}`' for name in state.缺失文件)}")

    prompt_lines.extend(
        [
            "",
            "## 执行要求",
            "- 对齐主文件内容，以参考仓库对应 SDK 的最新版本为准。",
            "- 补齐 `sdk_client.py` 与 `test_client`，若当前项目缺失则从参考仓库的 api_sdk 下复制。",
            "- 对齐当前项目与参考仓库中对应 SDK 的所有文件。",
            "- 不要修改本项目中与上述 SDK 无关的内容。",
            "- 更新后保持文件结构与命名一致。",
            "- 完成 SDK 本体调整后，检查所有调用这些 SDK 的地方，并将调用改为最新方式。",
            "- 重点确认更新后是否需要实例化，以及调用方式是否发生变化。",
        ]
    )
    return "\n".join(prompt_lines)


def main() -> None:
    try:
        target_dir = _resolve_target_dir(sys.argv)
    except ValueError as exc:
        print(str(exc))
        sys.exit(1)
    except NotADirectoryError as exc:
        print(f"错误: {exc}")
        sys.exit(1)

    ok, message = _update_reference_repo()
    if not ok:
        print("更新失败，请重试")
        if message:
            print(message)
        sys.exit(1)

    sdk_root = target_dir / "src" / "sdk"
    if not sdk_root.is_dir():
        print("无法扫描：未找到 `src/sdk` 目录。")
        sys.exit(1)

    sdk_dirs = _iter_sdk_dirs(sdk_root, target_dir.name)
    states = [_build_state(sdk_dir, _api_sdk_python_root()) for sdk_dir in sdk_dirs]
    unable_states = [state for state in states if state.判定 == "无法判断"]

    prompt = _format_prompt(target_dir, _api_sdk_python_root(), states, unable_states)
    print(prompt)

    if any(state.判定 == "未升级" for state in states):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
