"""
# PRD（开发规范引用）
请在阅读本脚本具体功能前，务必先查看并遵守 `PRD_COMMON.md` 中的“通用开发规范”。

# 脚本具体 PRD: 外部SDK升级检查器

## 1. 目标
在目标项目中检查外部 SDK 是否需要升级。
如果存在需要升级的 SDK，则输出一段可直接交给 AI Agent 的“升级处理提示词”，用于驱动后续代码改造。
如果不存在需要升级的 SDK，则输出“检查通过”的提示并正常结束。

## 2. 检查规则
- **检查范围**：目标项目的 `src/sdk` 目录下所有非隐藏 SDK 目录。
- **对齐依据**：以参考仓库中的对应 SDK 为准。
- **识别原则**：只要当前项目中的 SDK 与参考版本不一致，或缺少对应主文件，就视为需要升级处理。
- **无法判断**：当目标 SDK 无法在参考仓库中找到对应项，或主文件无法读取时，标记为无法判断。
- **分组规则**：升级按固定分组输出提示词，`room / room_v10` 作为一组，`user_profile / user_profile_flask / user_profile_sanic` 作为一组。若同组只存在其中一个 SDK，也按该组提示词处理。
- **优先级规则**：专属分组只在没有其他未升级 SDK 时才进入处理；如果还存在其他未升级 SDK，先处理那些非专属分组的 SDK。
- **未保存修改检查**：在确认本轮要升级的 SDK 前，先检查目标项目 `src/sdk` 下是否已有未保存修改；若已有 SDK 升级改动，则先阻断并提示合并后再继续下一步。
- **特殊忽略项**：`room_sanic` 保持原有忽略行为，不参与本轮分组升级。

## 3. 命令行接口
- **用法**：`python 外部SDK升级检查器.py <target_directory>`
- **参数**：`<target_directory>` 是需要检查的项目目录。
- **默认行为**：如果未传入参数，则默认使用当前工作目录作为目标目录。

## 4. 预期效果
- 若未检测到需要升级的 SDK：输出“无需要升级的 SDK”的提示，并以 0 退出。
- 若检测到需要升级的 SDK：输出“外部 SDK 升级检查结果”提示，并以 1 退出。
- 若目标目录无效：输出错误信息，并以 1 退出。
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REFERENCE_REPO_ROOT = Path("/home/coder/github/kevinanew/api_sdk")
REFERENCE_SDK_ROOT = REFERENCE_REPO_ROOT / "python"
REFERENCE_SDK_ALIASES: dict[str, str] = {
    "room": "room_sanic",
    "room_v10": "room_sanic",
}


@dataclass(frozen=True)
class SDKUpgradeGroup:
    group_name: str
    sdk_names: tuple[str, ...]
    title: str
    overview_lines: tuple[str, ...]


SDK_UPGRADE_GROUPS: tuple[SDKUpgradeGroup, ...] = (
    SDKUpgradeGroup(
        group_name="room",
        sdk_names=("room", "room_v10"),
        title="room 组升级检查结果",
        overview_lines=(
            "- 本轮按 room 组处理，适用范围包含 room、room_v10，最终目标统一迁移到 room_sanic。",
            "- 即使当前项目只存在 room 组中的一个 SDK，也按本组提示词处理。",
            "- 本轮只处理本组命中的 SDK，不要把其他组的 SDK 混进来。",
        ),
    ),
    SDKUpgradeGroup(
        group_name="user_profile",
        sdk_names=("user_profile", "user_profile_flask", "user_profile_sanic"),
        title="user_profile 组升级检查结果",
        overview_lines=(
            "- 本轮按 user_profile 组处理，适用范围包含 user_profile、user_profile_flask、user_profile_sanic。",
            "- 即使当前项目只存在其中一个 SDK，也按本组提示词处理。",
            "- 本轮只处理本组命中的 SDK，不要把其他组的 SDK 混进来。",
        ),
    ),
)

# 保留旧脚本中未纳入本轮分组升级的特殊项。
IGNORED_SDK_NAMES = {"room_sanic"}


@dataclass(frozen=True)
class SDKStatus:
    sdk_name: str
    current_sdk_dir: Path
    current_main_file: Path | None
    reference_sdk_dir: Path | None
    reference_main_file: Path | None
    status: str
    reason: str = ""


def _run_command(command: list[str], cwd: Path) -> bool:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0


def update_reference_repo() -> bool:
    """更新参考仓库，失败时返回 False，但不中断后续流程。"""
    if not REFERENCE_REPO_ROOT.is_dir():
        return False

    commands = [
        ["git", "fetch", "origin"],
        ["git", "checkout", "master"],
        ["git", "reset", "--hard", "origin/master"],
    ]
    return all(_run_command(command, REFERENCE_REPO_ROOT) for command in commands)


def resolve_target_dir(raw_target: str | None) -> Path | None:
    """解析目标目录，默认当前工作目录。"""
    target = Path(raw_target) if raw_target else Path(".")
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()
    else:
        target = target.resolve()
    return target if target.is_dir() else None


def is_hidden_name(name: str) -> bool:
    return name.startswith(".") or name == "__pycache__"


def iter_sdk_dirs(sdk_root: Path, project_name: str) -> list[Path]:
    if not sdk_root.is_dir():
        return []

    sdk_dirs: list[Path] = []
    for child in sdk_root.iterdir():
        if not child.is_dir():
            continue
        if is_hidden_name(child.name):
            continue
        if child.name == project_name:
            continue
        if child.name in IGNORED_SDK_NAMES:
            continue
        sdk_dirs.append(child)

    return sorted(sdk_dirs, key=lambda path: path.name)


def resolve_reference_sdk_dir(reference_root: Path, sdk_name: str) -> Path | None:
    base_name = REFERENCE_SDK_ALIASES.get(sdk_name, sdk_name)
    for suffix in ("_flask", "_sanic"):
        if base_name.endswith(suffix):
            base_name = base_name[: -len(suffix)]
            break

    candidate_names = [
        f"{base_name}_flask",
        base_name,
        f"{base_name}_sanic",
    ]

    for candidate_name in candidate_names:
        candidate_dir = reference_root / candidate_name
        if candidate_dir.is_dir():
            return candidate_dir

    return None


def pick_main_file(sdk_dir: Path) -> Path | None:
    same_name_file = sdk_dir / f"{sdk_dir.name}.py"
    if same_name_file.is_file():
        return same_name_file

    init_file = sdk_dir / "__init__.py"
    if init_file.is_file():
        return init_file

    return None


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def collect_dirty_sdk_paths(target_dir: Path) -> list[str]:
    command = ["git", "status", "--porcelain", "--untracked-files=normal", "--", "src/sdk"]
    try:
        completed = subprocess.run(
            command,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []

    if completed.returncode != 0:
        return []

    dirty_paths: list[str] = []
    for line in completed.stdout.splitlines():
        if len(line) < 4:
            continue
        path_part = line[3:].strip()
        if not path_part:
            continue

        candidates = [candidate.strip() for candidate in path_part.split("->")]
        if any(candidate.startswith("src/sdk/") or candidate == "src/sdk" for candidate in candidates):
            dirty_paths.append(candidates[-1])

    return dirty_paths


def classify_sdk(sdk_dir: Path, reference_root: Path) -> SDKStatus:
    current_main = pick_main_file(sdk_dir)
    reference_sdk_dir = resolve_reference_sdk_dir(reference_root, sdk_dir.name)
    reference_main = pick_main_file(reference_sdk_dir) if reference_sdk_dir is not None else None

    if current_main is None:
        return SDKStatus(
            sdk_name=sdk_dir.name,
            current_sdk_dir=sdk_dir,
            current_main_file=None,
            reference_sdk_dir=reference_sdk_dir,
            reference_main_file=reference_main,
            status="unknown",
            reason="当前项目主文件缺失",
        )

    if reference_main is None:
        return SDKStatus(
            sdk_name=sdk_dir.name,
            current_sdk_dir=sdk_dir,
            current_main_file=current_main,
            reference_sdk_dir=reference_sdk_dir,
            reference_main_file=None,
            status="unknown",
            reason="参考仓库中按 _flask / 同名 / _sanic 优先级未找到对应 SDK",
        )

    current_text = read_text(current_main)
    reference_text = read_text(reference_main)
    if current_text is None or reference_text is None:
        return SDKStatus(
            sdk_name=sdk_dir.name,
            current_sdk_dir=sdk_dir,
            current_main_file=current_main,
            reference_sdk_dir=reference_sdk_dir,
            reference_main_file=reference_main,
            status="unknown",
            reason="主文件读取失败",
        )

    if current_text == reference_text:
        return SDKStatus(
            sdk_name=sdk_dir.name,
            current_sdk_dir=sdk_dir,
            current_main_file=current_main,
            reference_sdk_dir=reference_sdk_dir,
            reference_main_file=reference_main,
            status="up_to_date",
        )

    return SDKStatus(
        sdk_name=sdk_dir.name,
        current_sdk_dir=sdk_dir,
        current_main_file=current_main,
        reference_sdk_dir=reference_sdk_dir,
        reference_main_file=reference_main,
        status="outdated",
        reason="主文件内容存在差异",
    )


def collect_sdk_statuses(target_dir: Path) -> tuple[list[SDKStatus], list[SDKStatus], list[SDKStatus]]:
    sdk_root = target_dir / "src" / "sdk"
    sdk_dirs = iter_sdk_dirs(sdk_root, target_dir.name)
    results = [classify_sdk(sdk_dir, REFERENCE_SDK_ROOT) for sdk_dir in sdk_dirs]

    up_to_date = [result for result in results if result.status == "up_to_date"]
    outdated = [result for result in results if result.status == "outdated"]
    unknown = [result for result in results if result.status == "unknown"]
    return up_to_date, outdated, unknown


def select_upgrade_batch(outdated: list[SDKStatus]) -> tuple[SDKUpgradeGroup | None, list[SDKStatus], list[SDKStatus]]:
    grouped_sdk_names = {sdk_name for group in SDK_UPGRADE_GROUPS for sdk_name in group.sdk_names}
    non_group_outdated = [status for status in outdated if status.sdk_name not in grouped_sdk_names]
    if non_group_outdated:
        selected = non_group_outdated[:3]
        remaining = non_group_outdated[3:] + [status for status in outdated if status.sdk_name in grouped_sdk_names]
        return None, selected, remaining

    for group in SDK_UPGRADE_GROUPS:
        selected = [status for status in outdated if status.sdk_name in group.sdk_names]
        if selected:
            remaining = [status for status in outdated if status.sdk_name not in group.sdk_names]
            return group, selected, remaining

    selected = outdated[:3]
    remaining = outdated[3:]
    return None, selected, remaining


def format_sdk_bullets(sdk_names: Iterable[str]) -> list[str]:
    return [f"- {sdk_name}" for sdk_name in sdk_names]


def format_unknown_sdk_bullets(unknown: Iterable[SDKStatus]) -> list[str]:
    return [f"- {status.sdk_name}：{status.reason}" for status in unknown]


def build_prompt(
    target_dir: Path,
    selected: list[SDKStatus],
    unknown: list[SDKStatus],
    total_outdated: int,
    group: SDKUpgradeGroup | None = None,
) -> str:
    selected_names = [status.sdk_name for status in selected]
    omitted_count = max(total_outdated - len(selected_names), 0)

    lines: list[str] = [
        f"# 外部 SDK 升级检查结果{f' - {group.title}' if group is not None else ''}\n",
        "全程使用中文回答。\n",
    ]
    if group is not None:
        lines.extend(
            [
                "## 本轮分组说明",
                *group.overview_lines,
                "",
            ]
        )
        if group.group_name == "room":
            lines.extend(
                [
                    "## room 组迁移要求",
                    "- `room` 与 `room_v10` 都是待淘汰旧 SDK，最终目标是删除它们并统一迁移到 `room_sanic`。",
                    "- 先搜索并替换当前项目中所有 `sdk.room`、`sdk.room_v10` 的导入、实例化和调用点。",
                    "- 对 `room_sanic` 已经提供的等价能力，直接替换到新实现；不要把旧 SDK 的兼容壳继续扩散到新代码里。",
                    "- 对 `room` 独有但 `room_sanic` 没有的接口，不要回填到 `room_sanic`，应先改造调用方或确认可以下线。",
                    "- 如果消费项目里还保留异步适配层，只允许放在消费项目内做薄封装，不要污染 `room_sanic` 本体。",
                    "",
                ]
            )
    lines.append("## 本次需要处理的 SDK")
    lines.extend(format_sdk_bullets(selected_names))
    lines.extend(
        [
            "",
            "## 当前项目信息",
            f"- 项目根目录：{target_dir}",
            f"- SDK 根目录：{target_dir / 'src' / 'sdk'}",
            f"- 当前项目名：{target_dir.name}\n",
            "## 参考仓库信息",
            f"- 仓库根目录：{REFERENCE_REPO_ROOT}",
            f"- Python SDK 根目录：{REFERENCE_SDK_ROOT}",
            "- 参考仓库 SDK 的选择优先级：先 `_flask`，其次完全同名，最后 `_sanic`；脚本会先自行判断",
            "- `room` 组的标准迁移目标是 `room_sanic`，不要再按同名旧壳理解 room 的升级任务",
            "- `sdk_client.py` 必须放在当前项目 `src/sdk/` 根目录下，所有 SDK 共用，不要放进某个 SDK 子目录\n",
            "## 处理要求",
            "- 先对齐上面列出的 SDK 及其同目录下的所有文件，以参考仓库最新内容为准。",
            "- 若当前项目缺少 `sdk_client.py` 或 `test_sdk_client.py`，从api_sdk参考仓库的根目录中，把 `sdk_client.py` 放到当前项目的 `src/sdk/` 目录下。",
            "- 检查当前项目中所有调用这些 SDK 的地方，并将调用调整为最新实例化方式与调用方式。",
            "- 保持文件结构与命名一致，不要修改这些 SDK 之外的内容。",
            "- 优化 SDK 调用点时尽量内敛修改，减少无意义中间变量的使用",
            "- SDK 异常处理必须使用 sdk_client.py 中的 SDKException ，严禁使用 sdk/exception.py",
            "- 如果你在参考仓库中找不到 `api_sdk` 项目，或者找不到对应 SDK，请返回错误码 `1` 退出。",
            "- 升级完成后严禁重复运行此脚本。直接激活 code_quality_checker skill 进行代码质量检查",
        ]
    )

    if omitted_count > 0:
        lines.extend(
            [
                "",
                "## 本轮未纳入的未升级 SDK",
                f"- 其余 {omitted_count} 个未升级 SDK 留待下一轮处理。",
            ]
        )

    if unknown:
        lines.extend(
            [
                "",
                "## 无法判断的 SDK",
            ]
        )
        lines.extend(format_unknown_sdk_bullets(unknown))

    return "\n".join(lines).rstrip()


def build_in_progress_message(dirty_paths: list[str]) -> str:
    lines: list[str] = [
        "# 当前正在升级 SDK",
        "当前正在升级SDK，请将未保存修改合并后再进行下一步SDK升级。",
    ]
    if dirty_paths:
        lines.extend(
            [
                "",
                "## 未保存修改区中的 SDK 改动",
            ]
        )
        lines.extend(format_sdk_bullets(dirty_paths))

    lines.extend(
        [
            "",
            "## 处理要求",
            "- 先将上述未保存修改合并完成，确认 `src/sdk` 下没有正在进行中的 SDK 升级改动后，再重新运行检查器。",
        ]
    )

    return "\n".join(lines).rstrip()


def build_no_upgrade_message(unknown: list[SDKStatus]) -> str:
    lines = ["无需要升级的 SDK"]
    if unknown:
        lines.extend(
            [
                "",
                "## 无法判断的 SDK",
            ]
        )
        lines.extend(format_unknown_sdk_bullets(unknown))
    return "\n".join(lines).rstrip()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv[1:]
    if len(args) > 1:
        print("用法: python code_doctor/外部SDK升级检查器.py [target_directory]")
        return 1

    target_dir = resolve_target_dir(args[0] if args else None)
    if target_dir is None:
        raw_target = args[0] if args else "."
        print(f"错误: '{raw_target}' 不是一个有效的目录。")
        return 1

    dirty_sdk_paths = collect_dirty_sdk_paths(target_dir)
    if dirty_sdk_paths:
        print(build_in_progress_message(dirty_sdk_paths))
        return 1

    update_reference_repo()

    _, outdated, unknown = collect_sdk_statuses(target_dir)
    if not outdated:
        print(build_no_upgrade_message(unknown))
        return 0

    group, selected, _ = select_upgrade_batch(outdated)
    if group is None:
        print(build_prompt(target_dir, selected, unknown, len(outdated)))
        return 1

    print(build_prompt(target_dir, selected, unknown, len(outdated), group=group))
    return 1


if __name__ == "__main__":
    sys.exit(main())
