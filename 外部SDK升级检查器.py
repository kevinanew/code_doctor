from __future__ import annotations

import difflib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REFERENCE_REPO_ROOT = Path("/home/coder/github/kevinanew/api_sdk")
REFERENCE_SDK_ROOT = REFERENCE_REPO_ROOT / "python"

IGNORED_SDK_NAMES = {"room_sanic"}


@dataclass(frozen=True)
class SDKUpgradeGroup:
    group_name: str
    sdk_names: tuple[str, ...]
    reference_sdk_name: str
    title: str
    overview_lines: tuple[str, ...]
    migration_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class SDKStatus:
    sdk_name: str
    current_sdk_dir: Path
    current_main_file: Path | None
    reference_sdk_dir: Path | None
    reference_main_file: Path | None
    status: str
    reason: str = ""


@dataclass(frozen=True)
class UpgradeBatch:
    group: SDKUpgradeGroup | None
    selected: list[SDKStatus]
    remaining: list[SDKStatus]


SDK_UPGRADE_GROUPS: tuple[SDKUpgradeGroup, ...] = (
    SDKUpgradeGroup(
        group_name="room",
        sdk_names=("room", "room_v10"),
        reference_sdk_name="room_sanic",
        title="room 组升级检查结果",
        overview_lines=(
            "- 本轮按 room 组处理，适用范围包含 room、room_v10，最终目标统一迁移到 room_sanic。",
            "- 即使当前项目只存在 room 组中的一个 SDK，也按本组提示词处理。",
            "- 本轮只处理本组命中的 SDK，不要把其他组的 SDK 混进来。",
        ),
        migration_lines=(
            "## room 组迁移要求",
            "- `room` 与 `room_v10` 都是待淘汰旧 SDK，最终目标是删除它们并统一迁移到 `room_sanic`。",
            "- 先搜索并替换当前项目中所有 `sdk.room`、`sdk.room_v10` 的导入、实例化和调用点。",
            "- 对 `room_sanic` 已经提供的等价能力，直接替换到新实现；不要把旧 SDK 的兼容壳继续扩散到新代码里。",
            "- 对 `room` 独有但 `room_sanic` 没有的接口，不要回填到 `room_sanic`，应先改造调用方或确认可以下线。",
            "- 遇到 room 相关的异步调用时，先判断异步是否真的带来并发或非阻塞价值；如果只是同步 SDK 调用，优先直接调用同步方法，不要为了保持 `async` 形式而额外套 `await asyncio.to_thread` 或类似封装。",
            "- 如果消费项目里还保留异步适配层，只允许放在消费项目内做薄封装，不要污染 `room_sanic` 本体。",
        ),
    ),
    SDKUpgradeGroup(
        group_name="user_profile",
        sdk_names=("user_profile", "user_profile_flask", "user_profile_sanic"),
        reference_sdk_name="user_profile_flask",
        title="user_profile 组升级检查结果",
        overview_lines=(
            "- 本轮按 user_profile 组处理，适用范围包含 user_profile、user_profile_sanic，最终目标统一迁移到 user_profile_flask。",
            "- 即使当前项目只存在其中一个 SDK，也按本组提示词处理。",
            "- 本轮只处理本组命中的 SDK，不要把其他组的 SDK 混进来。",
        ),
        migration_lines=(
            "## user_profile 组迁移要求",
            "- `user_profile` 与 `user_profile_sanic` 都是待统一的旧形态，最终目标是收敛到 `user_profile_flask`。",
            "- 先搜索并替换当前项目中所有 `sdk.user_profile`、`sdk.user_profile_sanic` 的导入、实例化和调用点。",
            "- 对 `user_profile_flask` 已经提供的等价能力，直接替换到新实现；不要把旧 SDK 的兼容壳继续扩散到新代码里。",
            "- 如果消费项目里还保留异步适配层，只允许放在消费项目内做薄封装，不要污染 `user_profile_flask` 本体。",
        ),
    ),
)


class PromptLibrary:
    HEADER = "# 外部 SDK 升级检查结果"
    CHINESE_ONLY = "全程使用中文回答。"

    @classmethod
    def build_in_progress_message(cls, dirty_paths: list[str]) -> str:
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
            lines.extend(f"- {path}" for path in dirty_paths)

        lines.extend(
            [
                "",
                "## 处理要求",
                "- 先将上述未保存修改合并完成，确认 `src/sdk` 下没有正在进行中的 SDK 升级改动后，再重新运行检查器。",
            ]
        )
        return "\n".join(lines).rstrip()

    @classmethod
    def build_no_upgrade_message(cls, unknown: Iterable[SDKStatus]) -> str:
        lines = ["没有需要升级的 SDK"]
        unknown_lines = [f"- {status.sdk_name}：{status.reason}" for status in unknown]
        if unknown_lines:
            lines.extend(["", "## 无法判断的 SDK", *unknown_lines])
        return "\n".join(lines).rstrip()

    @classmethod
    def build_upgrade_prompt(
        cls,
        target_dir: Path,
        selected: list[SDKStatus],
        unknown: list[SDKStatus],
        total_outdated: int,
        group: SDKUpgradeGroup | None = None,
    ) -> str:
        selected_names = [status.sdk_name for status in selected]
        omitted_count = max(total_outdated - len(selected_names), 0)

        lines: list[str] = [
            f"{cls.HEADER}{f' - {group.title}' if group is not None else ''}",
            cls.CHINESE_ONLY,
        ]

        if group is not None:
            lines.extend(["## 本轮分组说明", *group.overview_lines, ""])
            if group.migration_lines:
                lines.extend([*group.migration_lines, ""])

        lines.extend(
            [
                "## 本次需要处理的 SDK",
                *[f"- {sdk_name}" for sdk_name in selected_names],
                "",
                "## 当前项目信息",
                f"- 项目根目录：{target_dir}",
                f"- SDK 根目录：{target_dir / 'src' / 'sdk'}",
                f"- 当前项目名：{target_dir.name}",
                "",
                "## 参考仓库信息",
                f"- 仓库根目录：{REFERENCE_REPO_ROOT}",
                f"- Python SDK 根目录：{REFERENCE_SDK_ROOT}",
                f"- 当前分组的标准迁移目标：{group.reference_sdk_name if group is not None else '按普通 SDK 规则匹配'}",
                "- 普通 SDK 的参考仓库选择优先级：先 `_flask`，其次完全同名，最后 `_sanic`；脚本会先自行判断",
                "- `sdk_client.py` 必须放在当前项目 `src/sdk/` 根目录下，所有 SDK 共用，不要放进某个 SDK 子目录",
                "",
                "## 处理要求",
                "- 先对齐上面列出的 SDK 及其同目录下的所有文件，以参考仓库最新内容为准。",
                "- 若当前项目缺少 `sdk_client.py` 或 `test_sdk_client.py`，从 api_sdk 参考仓库复制到当前项目的 `src/sdk/` 根目录下。",
                "- 检查当前项目中所有调用这些 SDK 的地方，并将调用调整为最新实例化方式与调用方式。",
                "- 保持文件结构与命名一致，不要修改这些 SDK 之外的内容。",
                "- 优化 SDK 调用点时尽量内敛修改，减少无意义中间变量的使用。",
                "- SDK 异常处理必须使用 sdk_client.py 中的 SDKException，严禁使用 sdk/exception.py。",
                "- 如果你在参考仓库中找不到 `api_sdk` 项目，或者找不到对应 SDK，请返回错误码 `1` 退出。",
                "- 升级完成后严禁重复运行此脚本。直接激活 code_quality_checker skill 进行代码质量检查。",
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
            lines.extend(f"- {status.sdk_name}：{status.reason}" for status in unknown)

        return "\n".join(lines).rstrip()


class ExternalSDKUpgradeChecker:
    def __init__(
        self,
        target_dir: Path,
        reference_repo_root: Path,
        reference_sdk_root: Path,
    ) -> None:
        self.target_dir = target_dir
        self.reference_repo_root = reference_repo_root
        self.reference_sdk_root = reference_sdk_root

    @staticmethod
    def resolve_target_dir(raw_target: str | None) -> Path | None:
        target = Path(raw_target) if raw_target else Path(".")
        if not target.is_absolute():
            target = (Path.cwd() / target).resolve()
        else:
            target = target.resolve()
        return target if target.is_dir() else None

    @staticmethod
    def is_hidden_name(name: str) -> bool:
        return name.startswith(".") or name == "__pycache__"

    @staticmethod
    def pick_main_file(sdk_dir: Path) -> Path | None:
        same_name_file = sdk_dir / f"{sdk_dir.name}.py"
        if same_name_file.is_file():
            return same_name_file

        init_file = sdk_dir / "__init__.py"
        if init_file.is_file():
            return init_file

        return None

    @staticmethod
    def read_text(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    @staticmethod
    def count_diff_lines(current_text: str, reference_text: str) -> int:
        matcher = difflib.SequenceMatcher(None, current_text.splitlines(), reference_text.splitlines())
        diff_lines = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != "equal":
                diff_lines += max(i2 - i1, j2 - j1)
        return diff_lines

    def update_reference_repo(self) -> bool:
        if not self.reference_repo_root.is_dir():
            return False

        commands = (
            ["git", "fetch", "origin"],
            ["git", "checkout", "master"],
            ["git", "reset", "--hard", "origin/master"],
        )
        for command in commands:
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(self.reference_repo_root),
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                return False
            if completed.returncode != 0:
                return False
        return True

    def collect_dirty_sdk_paths(self) -> list[str]:
        command = ["git", "status", "--porcelain", "--untracked-files=normal", "--", "src/sdk"]
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.target_dir),
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

    def iter_sdk_dirs(self) -> list[Path]:
        sdk_root = self.target_dir / "src" / "sdk"
        if not sdk_root.is_dir():
            return []

        sdk_dirs: list[Path] = []
        for child in sdk_root.iterdir():
            if not child.is_dir():
                continue
            if self.is_hidden_name(child.name):
                continue
            if child.name == self.target_dir.name:
                continue
            if child.name in IGNORED_SDK_NAMES:
                continue
            sdk_dirs.append(child)
        return sorted(sdk_dirs, key=lambda path: path.name)

    @staticmethod
    def resolve_upgrade_group(sdk_name: str) -> SDKUpgradeGroup | None:
        for group in SDK_UPGRADE_GROUPS:
            if sdk_name in group.sdk_names:
                return group
        return None

    def resolve_reference_sdk_dir(self, sdk_name: str) -> Path | None:
        group = self.resolve_upgrade_group(sdk_name)
        if group is not None:
            candidate_names = (group.reference_sdk_name,)
        else:
            base_name = sdk_name
            for suffix in ("_flask", "_sanic"):
                if base_name.endswith(suffix):
                    base_name = base_name[: -len(suffix)]
                    break

            candidate_names = (f"{base_name}_flask", base_name, f"{base_name}_sanic")

        for candidate_name in candidate_names:
            candidate_dir = self.reference_sdk_root / candidate_name
            if candidate_dir.is_dir():
                return candidate_dir
        return None

    def classify_sdk(self, sdk_dir: Path) -> SDKStatus:
        current_main = self.pick_main_file(sdk_dir)
        reference_sdk_dir = self.resolve_reference_sdk_dir(sdk_dir.name)
        reference_main = self.pick_main_file(reference_sdk_dir) if reference_sdk_dir is not None else None

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

        current_text = self.read_text(current_main)
        reference_text = self.read_text(reference_main)
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

        if self.count_diff_lines(current_text, reference_text) <= 3:
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

    def collect_sdk_statuses(self) -> tuple[list[SDKStatus], list[SDKStatus], list[SDKStatus]]:
        results = [self.classify_sdk(sdk_dir) for sdk_dir in self.iter_sdk_dirs()]
        up_to_date = [result for result in results if result.status == "up_to_date"]
        outdated = [result for result in results if result.status == "outdated"]
        unknown = [result for result in results if result.status == "unknown"]
        return up_to_date, outdated, unknown

    def select_upgrade_batch(self, outdated: list[SDKStatus]) -> UpgradeBatch:
        grouped_sdk_names = {sdk_name for group in SDK_UPGRADE_GROUPS for sdk_name in group.sdk_names}
        non_group_outdated = [status for status in outdated if status.sdk_name not in grouped_sdk_names]
        if non_group_outdated:
            selected = non_group_outdated[:3]
            remaining = non_group_outdated[3:] + [status for status in outdated if status.sdk_name in grouped_sdk_names]
            return UpgradeBatch(group=None, selected=selected, remaining=remaining)

        for group in SDK_UPGRADE_GROUPS:
            selected = [status for status in outdated if status.sdk_name in group.sdk_names]
            if selected:
                remaining = [status for status in outdated if status.sdk_name not in group.sdk_names]
                return UpgradeBatch(group=group, selected=selected, remaining=remaining)

        return UpgradeBatch(group=None, selected=outdated[:3], remaining=outdated[3:])

    def run(self) -> int:
        dirty_sdk_paths = collect_dirty_sdk_paths(self.target_dir)
        if dirty_sdk_paths:
            print(build_in_progress_message(dirty_sdk_paths))
            return 1

        update_reference_repo()

        _, outdated, unknown = collect_sdk_statuses(self.target_dir)
        if not outdated:
            print(build_no_upgrade_message(unknown))
            return 0

        batch = select_upgrade_batch(outdated)
        print(
            build_prompt(
                self.target_dir,
                batch[1],
                unknown,
                len(outdated),
                group=batch[0],
            )
        )
        return 1


def resolve_target_dir(raw_target: str | None) -> Path | None:
    return ExternalSDKUpgradeChecker.resolve_target_dir(raw_target)


def pick_main_file(sdk_dir: Path) -> Path | None:
    return ExternalSDKUpgradeChecker.pick_main_file(sdk_dir)


def read_text(path: Path) -> str | None:
    return ExternalSDKUpgradeChecker.read_text(path)


def collect_dirty_sdk_paths(target_dir: Path) -> list[str]:
    checker = ExternalSDKUpgradeChecker(target_dir, REFERENCE_REPO_ROOT, REFERENCE_SDK_ROOT)
    return checker.collect_dirty_sdk_paths()


def resolve_reference_sdk_dir(reference_root: Path, sdk_name: str) -> Path | None:
    checker = ExternalSDKUpgradeChecker(Path("."), REFERENCE_REPO_ROOT, reference_root)
    return checker.resolve_reference_sdk_dir(sdk_name)


def classify_sdk(sdk_dir: Path, reference_root: Path) -> SDKStatus:
    checker = ExternalSDKUpgradeChecker(Path("."), REFERENCE_REPO_ROOT, reference_root)
    return checker.classify_sdk(sdk_dir)


def collect_sdk_statuses(target_dir: Path) -> tuple[list[SDKStatus], list[SDKStatus], list[SDKStatus]]:
    checker = ExternalSDKUpgradeChecker(target_dir, REFERENCE_REPO_ROOT, REFERENCE_SDK_ROOT)
    return checker.collect_sdk_statuses()


def select_upgrade_batch(outdated: list[SDKStatus]) -> tuple[SDKUpgradeGroup | None, list[SDKStatus], list[SDKStatus]]:
    checker = ExternalSDKUpgradeChecker(Path("."), REFERENCE_REPO_ROOT, REFERENCE_SDK_ROOT)
    batch = checker.select_upgrade_batch(outdated)
    return batch.group, batch.selected, batch.remaining


def build_prompt(
    target_dir: Path,
    selected: list[SDKStatus],
    unknown: list[SDKStatus],
    total_outdated: int,
    group: SDKUpgradeGroup | None = None,
) -> str:
    return PromptLibrary.build_upgrade_prompt(target_dir, selected, unknown, total_outdated, group=group)


def build_in_progress_message(dirty_paths: list[str]) -> str:
    return PromptLibrary.build_in_progress_message(dirty_paths)


def build_no_upgrade_message(unknown: list[SDKStatus]) -> str:
    return PromptLibrary.build_no_upgrade_message(unknown)


def update_reference_repo() -> bool:
    checker = ExternalSDKUpgradeChecker(Path("."), REFERENCE_REPO_ROOT, REFERENCE_SDK_ROOT)
    return checker.update_reference_repo()


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

    checker = ExternalSDKUpgradeChecker(target_dir, REFERENCE_REPO_ROOT, REFERENCE_SDK_ROOT)
    return checker.run()


if __name__ == "__main__":
    sys.exit(main())
