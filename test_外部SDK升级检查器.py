import io
import importlib.util
import sys
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


def load_module():
    script_path = Path(__file__).with_name("外部SDK升级检查器.py")
    spec = importlib.util.spec_from_file_location("external_sdk_upgrade_checker", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestExternalSdkUpgradeChecker(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.workspace = Path(tempfile.mkdtemp())
        self.project_root = self.workspace / "sample_project"
        self.project_root.mkdir()
        self.current_sdk_root = self.project_root / "src" / "sdk"
        self.current_sdk_root.mkdir(parents=True)

        self.reference_root = self.workspace / "api_sdk"
        self.reference_sdk_root = self.reference_root / "python"
        self.reference_sdk_root.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.workspace)

    def write_file(self, base: Path, relative_path: str, content: str) -> Path:
        path = base / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def multi_line_content(self, prefix: str, lines: int) -> str:
        return "\n".join(f"{prefix} {index}" for index in range(lines)) + "\n"

    def test_pick_main_file_prefers_same_named_py(self):
        sdk_dir = self.current_sdk_root / "app_user_flask"
        sdk_dir.mkdir()
        same_named = self.write_file(sdk_dir, "app_user_flask.py", "print('main')\n")
        self.write_file(sdk_dir, "__init__.py", "print('init')\n")

        picked = self.module.ExternalSDKUpgradeChecker.pick_main_file(sdk_dir)

        self.assertEqual(picked, same_named)

    def test_resolve_reference_sdk_dir_prefers_flask_then_same_then_sanic(self):
        self.write_file(self.reference_sdk_root, "sample_flask/sample_flask.py", "value = 1\n")
        self.write_file(self.reference_sdk_root, "sample/sample.py", "value = 2\n")
        self.write_file(self.reference_sdk_root, "sample_sanic/sample_sanic.py", "value = 3\n")

        checker = self.module.ExternalSDKUpgradeChecker(Path("."), self.module.REFERENCE_REPO_ROOT, self.reference_sdk_root)
        resolved = checker.resolve_reference_sdk_dir("sample")

        self.assertEqual(resolved, self.reference_sdk_root / "sample_flask")

    def test_resolve_reference_sdk_dir_falls_back_to_same_name_then_sanic(self):
        self.write_file(self.reference_sdk_root, "demo/demo.py", "value = 2\n")
        self.write_file(self.reference_sdk_root, "demo_sanic/demo_sanic.py", "value = 3\n")

        checker = self.module.ExternalSDKUpgradeChecker(Path("."), self.module.REFERENCE_REPO_ROOT, self.reference_sdk_root)
        resolved = checker.resolve_reference_sdk_dir("demo")

        self.assertEqual(resolved, self.reference_sdk_root / "demo")

    def test_resolve_reference_sdk_dir_maps_room_sdks_to_room_sanic(self):
        self.write_file(self.reference_sdk_root, "room_sanic/room_sanic.py", "value = 3\n")

        for sdk_name in ("room", "room_v10"):
            with self.subTest(sdk_name=sdk_name):
                checker = self.module.ExternalSDKUpgradeChecker(Path("."), self.module.REFERENCE_REPO_ROOT, self.reference_sdk_root)
                resolved = checker.resolve_reference_sdk_dir(sdk_name)
                self.assertEqual(resolved, self.reference_sdk_root / "room_sanic")

    def test_resolve_reference_sdk_dir_maps_user_profile_sdks_to_user_profile_flask(self):
        self.write_file(self.reference_sdk_root, "user_profile_flask/user_profile_flask.py", "value = 3\n")

        for sdk_name in ("user_profile", "user_profile_sanic"):
            with self.subTest(sdk_name=sdk_name):
                checker = self.module.ExternalSDKUpgradeChecker(Path("."), self.module.REFERENCE_REPO_ROOT, self.reference_sdk_root)
                resolved = checker.resolve_reference_sdk_dir(sdk_name)
                self.assertEqual(resolved, self.reference_sdk_root / "user_profile_flask")

    def test_resolve_reference_repo_root_prefers_home_github_path(self):
        home_root = self.workspace / "home"
        api_sdk_root = home_root / "github" / "kevinanew" / "api_sdk"
        self.write_file(api_sdk_root, "python/.keep", "")

        with patch.object(self.module.Path, "home", return_value=home_root), patch.object(
            self.module, "REFERENCE_REPO_CANDIDATES", (self.workspace / "missing_api_sdk", api_sdk_root)
        ):
            resolved = self.module.ExternalSDKUpgradeChecker.resolve_reference_repo_root()

        self.assertEqual(resolved, api_sdk_root)

    def test_collect_sdk_statuses_filters_self_and_classifies(self):
        self.write_file(self.current_sdk_root, "sample_project/sample_project.py", "self = 1\n")
        self.write_file(self.current_sdk_root, "need_update/need_update.py", self.multi_line_content("current", 12))
        self.write_file(self.current_sdk_root, "already/already.py", self.multi_line_content("same", 3))
        self.write_file(self.current_sdk_root, "room/room.py", self.multi_line_content("room current", 12))
        self.write_file(self.current_sdk_root, "room_v10/room_v10.py", self.multi_line_content("room v10 current", 12))
        self.write_file(self.current_sdk_root, ".hidden/hidden.py", "skip = True\n")
        self.write_file(self.current_sdk_root, "__pycache__/cache.py", "skip = True\n")
        self.write_file(self.current_sdk_root, "unknown/unknown.py", "value = 3\n")

        self.write_file(self.reference_sdk_root, "need_update/need_update.py", self.multi_line_content("reference", 12))
        self.write_file(self.reference_sdk_root, "already/already.py", self.multi_line_content("same", 3))
        self.write_file(self.reference_sdk_root, "sample_project/sample_project.py", self.multi_line_content("ref", 3))
        self.write_file(self.reference_sdk_root, "room_sanic/room_sanic.py", self.multi_line_content("room reference", 12))

        with patch.object(self.module.ExternalSDKUpgradeChecker, "resolve_reference_repo_root", return_value=self.reference_root):
            checker = self.module.ExternalSDKUpgradeChecker(self.project_root, self.module.REFERENCE_REPO_ROOT, self.reference_sdk_root)
            up_to_date, outdated, unknown = checker.collect_sdk_statuses()

        self.assertEqual([item.sdk_name for item in up_to_date], ["already"])
        self.assertEqual([item.sdk_name for item in outdated], ["need_update", "room", "room_v10"])
        self.assertEqual([item.sdk_name for item in unknown], ["unknown"])

    def test_select_upgrade_batch_prefers_non_group_before_room_group(self):
        outdated = [
            self.module.SDKStatus("other_a", Path("/a"), Path("/a/a.py"), Path("/b/a"), Path("/b/a.py"), "outdated"),
            self.module.SDKStatus("room_v10", Path("/a"), Path("/a/b.py"), Path("/b/b"), Path("/b/b.py"), "outdated"),
            self.module.SDKStatus("user_profile", Path("/a"), Path("/a/c.py"), Path("/b/c"), Path("/b/c.py"), "outdated"),
            self.module.SDKStatus("other_b", Path("/a"), Path("/a/d.py"), Path("/b/d"), Path("/b/d.py"), "outdated"),
        ]

        checker = self.module.ExternalSDKUpgradeChecker(Path("."), self.module.REFERENCE_REPO_ROOT, self.reference_sdk_root)
        group, selected, remaining = checker.select_upgrade_batch(outdated)

        self.assertIsNone(group)
        self.assertEqual([item.sdk_name for item in selected], ["other_a", "other_b"])
        self.assertEqual([item.sdk_name for item in remaining], ["room_v10", "user_profile"])

    def test_select_upgrade_batch_uses_room_group_after_other_sdks_are_done(self):
        outdated = [
            self.module.SDKStatus("room", Path("/a"), Path("/a/a.py"), Path("/b/a"), Path("/b/a.py"), "outdated"),
            self.module.SDKStatus("room_v10", Path("/a"), Path("/a/b.py"), Path("/b/b"), Path("/b/b.py"), "outdated"),
            self.module.SDKStatus("user_profile", Path("/a"), Path("/a/c.py"), Path("/b/c"), Path("/b/c.py"), "outdated"),
        ]

        checker = self.module.ExternalSDKUpgradeChecker(Path("."), self.module.REFERENCE_REPO_ROOT, self.reference_sdk_root)
        group, selected, remaining = checker.select_upgrade_batch(outdated)

        self.assertIsNotNone(group)
        self.assertEqual(group.group_name, "room")
        self.assertEqual([item.sdk_name for item in selected], ["room", "room_v10"])
        self.assertEqual([item.sdk_name for item in remaining], ["user_profile"])

    def test_select_upgrade_batch_uses_user_profile_group_after_room_sdks_are_done(self):
        outdated = [
            self.module.SDKStatus("user_profile", Path("/a"), Path("/a/a.py"), Path("/b/a"), Path("/b/a.py"), "outdated"),
        ]

        checker = self.module.ExternalSDKUpgradeChecker(Path("."), self.module.REFERENCE_REPO_ROOT, self.reference_sdk_root)
        group, selected, remaining = checker.select_upgrade_batch(outdated)

        self.assertIsNotNone(group)
        self.assertEqual(group.group_name, "user_profile")
        self.assertEqual([item.sdk_name for item in selected], ["user_profile"])
        self.assertEqual(remaining, [])

    def test_select_upgrade_batch_uses_user_profile_group_after_normal_sdks(self):
        outdated = [
            self.module.SDKStatus("other_sdk", Path("/a"), Path("/a/a.py"), Path("/b/a"), Path("/b/a.py"), "outdated"),
            self.module.SDKStatus("user_profile_sanic", Path("/a"), Path("/a/b.py"), Path("/b/b"), Path("/b/b.py"), "outdated"),
        ]

        checker = self.module.ExternalSDKUpgradeChecker(Path("."), self.module.REFERENCE_REPO_ROOT, self.reference_sdk_root)
        group, selected, remaining = checker.select_upgrade_batch(outdated)

        self.assertIsNone(group)
        self.assertEqual([item.sdk_name for item in selected], ["other_sdk"])
        self.assertEqual([item.sdk_name for item in remaining], ["user_profile_sanic"])

    def test_build_prompt_uses_group_specific_header(self):
        selected = [
            self.module.SDKStatus("sdk_a", Path("/a"), Path("/a/a.py"), Path("/b/a"), Path("/b/a.py"), "outdated"),
            self.module.SDKStatus("sdk_b", Path("/a"), Path("/a/b.py"), Path("/b/b"), Path("/b/b.py"), "outdated"),
            self.module.SDKStatus("sdk_c", Path("/a"), Path("/a/c.py"), Path("/b/c"), Path("/b/c.py"), "outdated"),
        ]
        unknown = [
            self.module.SDKStatus("sdk_z", Path("/a"), None, None, None, "unknown", "当前项目主文件缺失"),
        ]

        prompt = self.module.PromptLibrary.render_prompt(self.project_root, selected, unknown, 4, self.module.SDK_UPGRADE_GROUPS[0])

        self.assertIn("- sdk_a", prompt)
        self.assertIn("- sdk_b", prompt)
        self.assertIn("- sdk_c", prompt)
        self.assertNotIn("- sdk_d", prompt)
        self.assertIn("其余 1 个未升级 SDK 留待下一轮处理。", prompt)
        self.assertIn("## 无法判断的 SDK", prompt)
        self.assertIn("- sdk_z：当前项目主文件缺失", prompt)
        self.assertIn("room 组升级检查结果", prompt)
        self.assertIn("本轮按 room 组处理", prompt)
        self.assertIn("room 组迁移要求", prompt)
        self.assertIn("统一迁移到 room_sanic", prompt)
        self.assertIn("当前分组的标准迁移目标：room_sanic", prompt)
        self.assertIn("普通 SDK 的参考仓库选择优先级：先 `_flask`，其次完全同名，最后 `_sanic`", prompt)
        self.assertIn("src/sdk/` 根目录下，所有 SDK 共用", prompt)

    def test_build_prompt_uses_user_profile_group_specific_header(self):
        selected = [
            self.module.SDKStatus("user_profile_sanic", Path("/a"), Path("/a/a.py"), Path("/b/a"), Path("/b/a.py"), "outdated"),
        ]

        prompt = self.module.PromptLibrary.render_prompt(self.project_root, selected, [], 1, self.module.SDK_UPGRADE_GROUPS[1])

        self.assertIn("user_profile 组升级检查结果", prompt)
        self.assertIn("统一迁移到 user_profile_flask", prompt)
        self.assertIn("当前分组的标准迁移目标：user_profile_flask", prompt)

    def test_main_blocks_when_dirty_sdk_changes_exist(self):
        self.write_file(self.current_sdk_root, "room/room.py", "value = 1\n")

        buffer = io.StringIO()
        with patch.object(self.module.ExternalSDKUpgradeChecker, "collect_dirty_sdk_paths", return_value=["src/sdk/room/room.py"]), patch.object(
            self.module.ExternalSDKUpgradeChecker, "update_reference_repo", return_value=True
        ), redirect_stdout(buffer):
            return_code = self.module.main(["script", str(self.project_root)])

        self.assertEqual(return_code, 1)
        self.assertIn("当前正在升级SDK，请将未保存修改合并后再进行下一步SDK升级。", buffer.getvalue())
        self.assertIn("src/sdk/room/room.py", buffer.getvalue())

    def test_main_returns_zero_when_no_upgrade(self):
        self.write_file(self.current_sdk_root, "other_sdk/other_sdk.py", "value = 1\n")
        self.write_file(self.reference_sdk_root, "other_sdk/other_sdk.py", "value = 1\n")
        self.write_file(self.current_sdk_root, "room/room.py", "value = 10\n")
        self.write_file(self.reference_sdk_root, "room_sanic/room_sanic.py", "value = 10\n")

        buffer = io.StringIO()
        with patch.object(self.module.ExternalSDKUpgradeChecker, "resolve_reference_repo_root", return_value=self.reference_root), patch.object(
            self.module.ExternalSDKUpgradeChecker, "collect_dirty_sdk_paths", return_value=[]
        ), patch.object(self.module.ExternalSDKUpgradeChecker, "update_reference_repo", return_value=True), redirect_stdout(buffer):
            return_code = self.module.main(["script", str(self.project_root)])

        self.assertEqual(return_code, 0)
        self.assertIn("无需要升级的 SDK", buffer.getvalue())
        self.assertNotIn("## 已排除的 SDK", buffer.getvalue())

    def test_main_returns_zero_when_reference_repo_missing(self):
        buffer = io.StringIO()
        with patch.object(self.module.ExternalSDKUpgradeChecker, "resolve_reference_repo_root", return_value=None), redirect_stdout(buffer):
            return_code = self.module.main(["script", str(self.project_root)])

        self.assertEqual(return_code, 0)
        self.assertIn("未找到 api_sdk 参考项目，跳过非本项目 SDK 升级检查。", buffer.getvalue())
        self.assertNotIn("无需要升级的 SDK", buffer.getvalue())

    def test_main_returns_one_when_outdated_sdk_exists(self):
        self.write_file(self.current_sdk_root, "other_sdk/other_sdk.py", self.multi_line_content("current", 12))
        self.write_file(self.reference_sdk_root, "other_sdk/other_sdk.py", self.multi_line_content("reference", 12))
        self.write_file(self.current_sdk_root, "room/room.py", self.multi_line_content("same", 3))
        self.write_file(self.reference_sdk_root, "room_sanic/room_sanic.py", self.multi_line_content("same", 3))

        buffer = io.StringIO()
        with patch.object(self.module.ExternalSDKUpgradeChecker, "resolve_reference_repo_root", return_value=self.reference_root), patch.object(
            self.module.ExternalSDKUpgradeChecker, "collect_dirty_sdk_paths", return_value=[]
        ), patch.object(self.module.ExternalSDKUpgradeChecker, "update_reference_repo", return_value=True), redirect_stdout(buffer):
            return_code = self.module.main(["script", str(self.project_root)])

        self.assertEqual(return_code, 1)
        self.assertIn("other_sdk", buffer.getvalue())
        self.assertNotIn("## 已排除的 SDK", buffer.getvalue())

    def test_main_returns_one_when_room_group_outdated_exists(self):
        self.write_file(self.current_sdk_root, "room/room.py", self.multi_line_content("current", 12))
        self.write_file(self.reference_sdk_root, "room_sanic/room_sanic.py", self.multi_line_content("reference", 12))

        buffer = io.StringIO()
        with patch.object(self.module.ExternalSDKUpgradeChecker, "resolve_reference_repo_root", return_value=self.reference_root), patch.object(
            self.module.ExternalSDKUpgradeChecker, "collect_dirty_sdk_paths", return_value=[]
        ), patch.object(self.module.ExternalSDKUpgradeChecker, "update_reference_repo", return_value=True), redirect_stdout(buffer):
            return_code = self.module.main(["script", str(self.project_root)])

        self.assertEqual(return_code, 1)
        self.assertIn("room 组升级检查结果", buffer.getvalue())
        self.assertIn("- room", buffer.getvalue())

    def test_main_prefers_non_group_sdk_over_room_group(self):
        self.write_file(self.current_sdk_root, "room/room.py", self.multi_line_content("current", 12))
        self.write_file(self.reference_sdk_root, "room_sanic/room_sanic.py", self.multi_line_content("reference", 12))
        self.write_file(self.current_sdk_root, "other_sdk/other_sdk.py", self.multi_line_content("current", 12))
        self.write_file(self.reference_sdk_root, "other_sdk/other_sdk.py", self.multi_line_content("reference", 12))

        buffer = io.StringIO()
        with patch.object(self.module.ExternalSDKUpgradeChecker, "resolve_reference_repo_root", return_value=self.reference_root), patch.object(
            self.module.ExternalSDKUpgradeChecker, "collect_dirty_sdk_paths", return_value=[]
        ), patch.object(self.module.ExternalSDKUpgradeChecker, "update_reference_repo", return_value=True), redirect_stdout(buffer):
            return_code = self.module.main(["script", str(self.project_root)])

        self.assertEqual(return_code, 1)
        self.assertNotIn("room 组升级检查结果", buffer.getvalue())
        self.assertIn("other_sdk", buffer.getvalue())

    def test_count_diff_lines_treats_small_changes_as_no_upgrade(self):
        current_text = self.multi_line_content("line", 5)
        reference_text = self.multi_line_content("line", 5)

        self.assertEqual(self.module.ExternalSDKUpgradeChecker.diff_lines(current_text, reference_text), 0)

    def test_count_diff_lines_treats_large_changes_as_upgrade(self):
        current_text = self.multi_line_content("current", 12)
        reference_text = self.multi_line_content("reference", 12)

        self.assertGreater(self.module.ExternalSDKUpgradeChecker.diff_lines(current_text, reference_text), 10)


if __name__ == "__main__":
    unittest.main()
