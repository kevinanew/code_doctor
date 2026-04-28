"""外部 SDK 升级检查器。

用法:
    python code_doctor/外部SDK升级检查器.py [项目名]

说明:
    - 不传参数时，默认使用当前工作目录。
    - 脚本会尝试更新参考仓库 `/home/coder/github/kevinanew/api_sdk/python`
    - 只做检查和输出，不直接修改代码。

PRD 摘要:
    1. 目标
       - 检查当前项目 `src/sdk` 下的外部 SDK 是否落后于参考仓库。
       - 通过主文件内容差异判断是否升级。
       - 输出给 AI agent 使用的 Markdown 提示词。

    2. 运行约定
       - 更新参考仓库：`git fetch origin` -> `git checkout master` -> `git reset --hard origin/master`
       - 更新失败不阻断后续检查，只记录失败状态。
       - 输出只面向 stdout。
       - 无需升级时输出 `无需要升级的 SDK` 并返回 `0`。
       - 需要升级时输出对应提示词并返回 `1`。

    3. 检查规则
       - 扫描当前项目 `src/sdk` 下所有非隐藏目录。
       - 排除本项目 SDK、`room_sanic`、`__pycache__`、以及所有以 `.` 开头的文件和目录。
       - 主文件优先 `目录同名.py`，否则 `__init__.py`。
       - 主文件内容差异行数 `<= 10` 视为已升级，`> 10` 视为需要升级。
       - 一次最多处理 3 个未升级 SDK。
       - 若 `src/sdk` 中存在正在进行的 SDK 升级改动，先提示合并并停止本轮其他升级需求。
       - `sdk_client.py` 和 `test_sdk_client.py` 必须存在，且只能放在 `src/sdk/` 根目录。

    4. 架构要求
       - 必须使用面向对象组织代码。
       - 提示词统一集中管理。
       - 升级组通过统一策略表管理，普通 SDK 与专属组共用同一套选择机制。
       - 当前支持的专属组：
         - `room` / `room_v10` -> `room_sanic`
         - `user_profile` / `user_profile_sanic` -> `user_profile_flask`

    5. 提示词内容
       - 本次需要处理的 SDK 名称
       - 当前项目根目录与参考仓库目录
       - 参考仓库 SDK 的选择优先级
       - `sdk_client.py` / `test_sdk_client.py` 的放置边界
       - 对齐主文件、补齐缺失文件、保持目录结构一致、限制修改边界
       - 无法判断的 SDK 需单独列出并写明原因
"""

from __future__ import annotations

import difflib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REFERENCE_REPO_ROOT = Path("/home/coder/github/kevinanew/api_sdk")
REFERENCE_REPO_ROOT_HOME = Path.home() / "github" / "kevinanew" / "api_sdk"
REFERENCE_REPO_CANDIDATES = (REFERENCE_REPO_ROOT, REFERENCE_REPO_ROOT_HOME)
REFERENCE_SDK_ROOT = REFERENCE_REPO_ROOT / "python"
IGNORED_SDK_NAMES = {"room_sanic"}


@dataclass(frozen=True)
class SDKUpgradeGroup:
    """描述一个可被统一处理的 SDK 升级策略组。

    这个对象不是“业务实体”，而是“策略配置”。
    它负责把一组名字相近、但在升级时必须一起看待的 SDK 收束成统一规则。
    例如:
    - `room` / `room_v10` 最终统一到 `room_sanic`
    - `user_profile` / `user_profile_sanic` 最终统一到 `user_profile_flask`

    字段含义:
    - group_name: 组的内部标识
    - sdk_names: 当前项目中会命中的 SDK 名称集合
    - reference_sdk_name: 该组最终统一对齐的参考目录名
    - title: 输出提示词时的标题
    - overview: 给 AI agent 的分组说明，解释为什么要按这组处理
    - migration: 更细的迁移要求，必要时写清目标目录和调用替换方向
    """

    group_name: str
    sdk_names: tuple[str, ...]
    reference_sdk_name: str
    title: str
    overview: str
    migration: str = ""


@dataclass(frozen=True)
class SDKStatus:
    """描述一个 SDK 当前在检查过程中的状态。

    这个结构的作用是承载“扫描 -> 分类 -> 决策”过程中的中间结果。
    它既保留当前项目侧的信息，也保留参考仓库侧的信息，方便后续输出提示词。

    字段含义:
    - sdk_name: SDK 名称
    - current_sdk_dir: 当前项目中的 SDK 目录
    - current_main_file: 当前项目主文件
    - reference_sdk_dir: 参考仓库对应目录
    - reference_main_file: 参考仓库主文件
    - status: up_to_date / outdated / unknown
    - reason: 无法判断或不升级时的原因
    """

    sdk_name: str
    current_sdk_dir: Path
    current_main_file: Path | None
    reference_sdk_dir: Path | None
    reference_main_file: Path | None
    status: str
    reason: str = ""


# 统一升级策略表。
# 这里不要写成零散的 if/elif 分支，而是把“哪些 SDK 归为一组、组最终对齐到哪里、
# 需要给 AI agent 说明什么”都集中在一个地方，方便后续扩展类似 SDK。
SDK_UPGRADE_GROUPS = (
    SDKUpgradeGroup(
        "room",
        ("room", "room_v10"),
        "room_sanic",
        "room 组升级检查结果",
        "- 本轮按 room 组处理，适用范围包含 room、room_v10，最终目标统一迁移到 room_sanic。\n- 即使当前项目只存在 room 组中的一个 SDK，也按本组提示词处理。\n- 本轮只处理本组命中的 SDK，不要把其他组的 SDK 混进来。",
        "## room 组迁移要求\n- `room` 与 `room_v10` 都是待淘汰旧 SDK，最终目标是删除它们并统一迁移到 `room_sanic`。\n- 先搜索并替换当前项目中所有 `sdk.room`、`sdk.room_v10` 的导入、实例化和调用点。\n- 对 `room_sanic` 已经提供的等价能力，直接替换到新实现；不要把旧 SDK 的兼容壳继续扩散到新代码里。\n- 对 `room` 独有但 `room_sanic` 没有的接口，不要回填到 `room_sanic`，应先改造调用方或确认可以下线。\n- 遇到 room 相关的异步调用时，先判断异步是否真的带来并发或非阻塞价值；如果只是同步 SDK 调用，优先直接调用同步方法，不要为了保持 `async` 形式而额外套 `await asyncio.to_thread` 或类似封装。\n- 如果消费项目里还保留异步适配层，只允许放在消费项目内做薄封装，不要污染 `room_sanic` 本体。",
    ),
    SDKUpgradeGroup(
        "user_profile",
        ("user_profile", "user_profile_flask", "user_profile_sanic"),
        "user_profile_flask",
        "user_profile 组升级检查结果",
        "- 本轮按 user_profile 组处理，适用范围包含 user_profile、user_profile_sanic，最终目标统一迁移到 user_profile_flask。\n- 即使当前项目只存在其中一个 SDK，也按本组提示词处理。\n- 本轮只处理本组命中的 SDK，不要把其他组的 SDK 混进来。",
        "## user_profile 组迁移要求\n- `user_profile` 与 `user_profile_sanic` 都是待统一的旧形态，最终目标是收敛到 `user_profile_flask`。\n- 先搜索并替换当前项目中所有 `sdk.user_profile`、`sdk.user_profile_sanic` 的导入、实例化和调用点。\n- 对 `user_profile_flask` 已经提供的等价能力，直接替换到新实现；不要把旧 SDK 的兼容壳继续扩散到新代码里。\n- 如果消费项目里还保留异步适配层，只允许放在消费项目内做薄封装，不要污染 `user_profile_flask` 本体。",
    ),
)


class PromptLibrary:
    """负责把检查结果渲染成给 AI agent 读取的 Markdown 提示词。

    这个类只处理“输出长什么样”，不负责判断“该输出哪一组”。
    这样可以把规则判断和提示词拼装拆开，避免主流程和文案互相污染。
    """

    HEADER = "# 外部 SDK 升级检查结果"

    @staticmethod
    def render_in_progress(dirty_paths: list[str]) -> str:
        lines = [
            "# 当前正在升级 SDK",
            "当前正在升级SDK，请将未保存修改合并后再进行下一步SDK升级。",
        ]
        if dirty_paths:
            lines += ["", "## 未保存修改区中的 SDK 改动", *[f"- {p}" for p in dirty_paths]]
        lines += [
            "",
            "## 处理要求",
            "- 先将上述未保存修改合并完成，确认 `src/sdk` 下没有正在进行中的 SDK 升级改动后，再重新运行检查器。",
        ]
        return "\n".join(lines)

    @staticmethod
    def render_no_upgrade(unknown: list[SDKStatus]) -> str:
        lines = ["无需要升级的 SDK"]
        if unknown:
            lines += ["", "## 无法判断的 SDK", *[f"- {s.sdk_name}：{s.reason}" for s in unknown]]
        return "\n".join(lines)

    @staticmethod
    def render_prompt(
        target_dir: Path,
        selected: list[SDKStatus],
        unknown: list[SDKStatus],
        total_outdated: int,
        group: SDKUpgradeGroup | None = None,
    ) -> str:
        omitted = max(total_outdated - len(selected), 0)
        lines = [f"{PromptLibrary.HEADER}{f' - {group.title}' if group else ''}", "全程使用中文回答。"]
        if group:
            lines += ["## 本轮分组说明", *group.overview.splitlines()]
            if group.migration:
                lines += ["", *group.migration.splitlines()]
        lines += [
            "",
            "## 本次需要处理的 SDK",
            *[f"- {s.sdk_name}" for s in selected],
            "",
            "## 当前项目信息",
            f"- 项目根目录：{target_dir}",
            f"- SDK 根目录：{target_dir / 'src' / 'sdk'}",
            f"- 当前项目名：{target_dir.name}",
            "",
            "## 参考仓库信息",
            f"- 仓库根目录：{REFERENCE_REPO_ROOT}",
            f"- Python SDK 根目录：{REFERENCE_SDK_ROOT}",
            f"- 当前分组的标准迁移目标：{group.reference_sdk_name if group else '按普通 SDK 规则匹配'}",
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
            "- 如果你找不到对应 SDK，请返回错误码 `1` 退出。",
            "- 升级完成后严禁重复运行此脚本。直接激活 code_quality_checker skill 进行代码质量检查。",
        ]
        if omitted:
            lines += ["", "## 本轮未纳入的未升级 SDK", f"- 其余 {omitted} 个未升级 SDK 留待下一轮处理。"]
        if unknown:
            lines += ["", "## 无法判断的 SDK", *[f"- {s.sdk_name}：{s.reason}" for s in unknown]]
        return "\n".join(lines)


class ExternalSDKUpgradeChecker:
    """外部 SDK 升级检查器主类。

    职责边界:
    - 拉取并同步参考仓库
    - 扫描当前项目 `src/sdk`
    - 识别普通 SDK 与专属升级组
    - 比较主文件差异并判定是否升级
    - 组装最终提示词并决定退出码

    这个类应当被看作“检查流程总控”，而不是单个功能点集合。
    所有后续的新增专属组、阈值调整、提示词变化，都应优先从这里的流程入口理解。
    """

    def __init__(self, target_dir: Path, reference_repo_root: Path, reference_sdk_root: Path) -> None:
        self.target_dir = target_dir
        self.reference_repo_root = reference_repo_root
        self.reference_sdk_root = reference_sdk_root

    @staticmethod
    def resolve_reference_repo_root() -> Path | None:
        for candidate in REFERENCE_REPO_CANDIDATES:
            if candidate.is_dir() and (candidate / "python").is_dir():
                return candidate
        github_root = Path.home() / "github"
        if not github_root.is_dir():
            return None
        for candidate in sorted(path for path in github_root.rglob("api_sdk") if path.is_dir()):
            if (candidate / "python").is_dir():
                return candidate
        return None

    @staticmethod
    def resolve_target_dir(raw_target: str | None) -> Path | None:
        target = Path(raw_target) if raw_target else Path(".")
        target = (Path.cwd() / target if not target.is_absolute() else target).resolve()
        return target if target.is_dir() else None

    @staticmethod
    def pick_main_file(sdk_dir: Path | None) -> Path | None:
        if sdk_dir is None:
            return None
        same = sdk_dir / f"{sdk_dir.name}.py"
        if same.is_file():
            return same
        init = sdk_dir / "__init__.py"
        return init if init.is_file() else None

    @staticmethod
    def read_text(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    @staticmethod
    def diff_lines(current_text: str, reference_text: str) -> int:
        matcher = difflib.SequenceMatcher(None, current_text.splitlines(), reference_text.splitlines())
        return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal")

    @staticmethod
    def resolve_upgrade_group(sdk_name: str) -> SDKUpgradeGroup | None:
        return next((group for group in SDK_UPGRADE_GROUPS if sdk_name in group.sdk_names), None)

    def update_reference_repo(self) -> bool:
        if not self.reference_repo_root.is_dir():
            return False
        for command in (["git", "fetch", "origin"], ["git", "checkout", "master"], ["git", "reset", "--hard", "origin/master"]):
            try:
                if subprocess.run(command, cwd=self.reference_repo_root, capture_output=True, text=True).returncode != 0:
                    return False
            except OSError:
                return False
        return True

    def collect_dirty_sdk_paths(self) -> list[str]:
        try:
            completed = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=normal", "--", "src/sdk"],
                cwd=self.target_dir,
                capture_output=True,
                text=True,
            )
        except OSError:
            return []
        if completed.returncode != 0:
            return []
        dirty = []
        for line in completed.stdout.splitlines():
            path_part = line[3:].strip() if len(line) >= 4 else ""
            if not path_part:
                continue
            candidates = [item.strip() for item in path_part.split("->")]
            if any(item.startswith("src/sdk/") or item == "src/sdk" for item in candidates):
                dirty.append(candidates[-1])
        return dirty

    def iter_sdk_dirs(self) -> list[Path]:
        sdk_root = self.target_dir / "src" / "sdk"
        if not sdk_root.is_dir():
            return []
        return sorted(
            child
            for child in sdk_root.iterdir()
            if child.is_dir() and not child.name.startswith(".") and child.name != "__pycache__" and child.name != self.target_dir.name and child.name not in IGNORED_SDK_NAMES
        )

    def resolve_reference_sdk_dir(self, sdk_name: str) -> Path | None:
        group = self.resolve_upgrade_group(sdk_name)
        if group:
            candidate_names = (group.reference_sdk_name,)
        else:
            base_name = sdk_name
            for suffix in ("_flask", "_sanic"):
                if base_name.endswith(suffix):
                    base_name = base_name[: -len(suffix)]
                    break
            candidate_names = (f"{base_name}_flask", base_name, f"{base_name}_sanic")
        return next((self.reference_sdk_root / name for name in candidate_names if (self.reference_sdk_root / name).is_dir()), None)

    def classify_sdk(self, sdk_dir: Path) -> SDKStatus:
        current_main = self.pick_main_file(sdk_dir)
        reference_sdk_dir = self.resolve_reference_sdk_dir(sdk_dir.name)
        reference_main = self.pick_main_file(reference_sdk_dir)
        if current_main is None:
            return SDKStatus(sdk_dir.name, sdk_dir, None, reference_sdk_dir, reference_main, "unknown", "当前项目主文件缺失")
        if reference_main is None:
            return SDKStatus(sdk_dir.name, sdk_dir, current_main, reference_sdk_dir, None, "unknown", "参考仓库中按专属组或 _flask / 同名 / _sanic 优先级未找到对应 SDK")
        current_text, reference_text = self.read_text(current_main), self.read_text(reference_main)
        if current_text is None or reference_text is None:
            return SDKStatus(sdk_dir.name, sdk_dir, current_main, reference_sdk_dir, reference_main, "unknown", "主文件读取失败")
        if self.diff_lines(current_text, reference_text) <= 10:
            return SDKStatus(sdk_dir.name, sdk_dir, current_main, reference_sdk_dir, reference_main, "up_to_date")
        return SDKStatus(sdk_dir.name, sdk_dir, current_main, reference_sdk_dir, reference_main, "outdated", "主文件内容存在差异")

    def collect_sdk_statuses(self) -> tuple[list[SDKStatus], list[SDKStatus], list[SDKStatus]]:
        results = [self.classify_sdk(sdk_dir) for sdk_dir in self.iter_sdk_dirs()]
        return ([r for r in results if r.status == "up_to_date"], [r for r in results if r.status == "outdated"], [r for r in results if r.status == "unknown"])

    def select_upgrade_batch(self, outdated: list[SDKStatus]) -> tuple[SDKUpgradeGroup | None, list[SDKStatus], list[SDKStatus]]:
        grouped = {name for group in SDK_UPGRADE_GROUPS for name in group.sdk_names}
        non_group = [item for item in outdated if item.sdk_name not in grouped]
        if non_group:
            return None, non_group[:3], non_group[3:] + [item for item in outdated if item.sdk_name in grouped]
        for group in SDK_UPGRADE_GROUPS:
            selected = [item for item in outdated if item.sdk_name in group.sdk_names]
            if selected:
                return group, selected, [item for item in outdated if item.sdk_name not in group.sdk_names]
        return None, outdated[:3], outdated[3:]

    def run(self) -> int:
        if not self.reference_repo_root.is_dir():
            print("未找到 api_sdk 参考项目，跳过非本项目 SDK 升级检查。")
            return 0
        dirty = self.collect_dirty_sdk_paths()
        if dirty:
            print(PromptLibrary.render_in_progress(dirty))
            return 1
        self.update_reference_repo()
        _, outdated, unknown = self.collect_sdk_statuses()
        if not outdated:
            print(PromptLibrary.render_no_upgrade(unknown))
            return 0
        group, selected, _ = self.select_upgrade_batch(outdated)
        print(PromptLibrary.render_prompt(self.target_dir, selected, unknown, len(outdated), group))
        return 1


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv[1:]
    if len(args) > 1:
        print("用法: python code_doctor/外部SDK升级检查器.py [target_directory]")
        return 1
    target_dir = ExternalSDKUpgradeChecker.resolve_target_dir(args[0] if args else None)
    if target_dir is None:
        print(f"错误: '{args[0] if args else '.'}' 不是一个有效的目录。")
        return 1
    reference_repo_root = ExternalSDKUpgradeChecker.resolve_reference_repo_root()
    if reference_repo_root is None:
        print("未找到 api_sdk 参考项目，跳过非本项目 SDK 升级检查。")
        return 0
    return ExternalSDKUpgradeChecker(target_dir, reference_repo_root, reference_repo_root / "python").run()


if __name__ == "__main__":
    sys.exit(main())
