import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestExternalSDKUpgradeChecker(unittest.TestCase):
    def setUp(self):
        self.workdir = Path(tempfile.mkdtemp())
        self.target_root = self.workdir / "demo_project"
        self.target_root.mkdir(parents=True, exist_ok=True)
        self.target_sdk_root = self.target_root / "src" / "sdk"
        self.target_sdk_root.mkdir(parents=True, exist_ok=True)

        self.reference_root = self.workdir / "api_sdk"
        self.reference_sdk_root = self.reference_root / "python"
        self.reference_sdk_root.mkdir(parents=True, exist_ok=True)

        self.script_path = Path(__file__).with_name("外部SDK升级检查器.py")

    def tearDown(self):
        shutil.rmtree(self.workdir)

    def _write(self, base: Path, rel_path: str, content: str) -> None:
        path = base / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _run(self):
        env = os.environ.copy()
        env["CODE_DOCTOR_SKIP_API_SDK_UPDATE"] = "1"
        env["CODE_DOCTOR_API_SDK_REPO_ROOT"] = str(self.reference_root)
        return subprocess.run(
            ["python3", str(self.script_path), str(self.target_root)],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_no_upgrade_outputs_pass_message(self):
        self._write(
            self.target_sdk_root,
            "demo_project/demo_project.py",
            "print('same')\n",
        )
        self._write(
            self.reference_sdk_root,
            "demo_project/demo_project.py",
            "print('same')\n",
        )
        self._write(
            self.target_sdk_root,
            "alpha/alpha.py",
            "print('alpha current')\n",
        )
        self._write(
            self.reference_sdk_root,
            "alpha/alpha.py",
            "print('alpha current')\n",
        )

        result = self._run()
        self.assertEqual(result.returncode, 0)
        self.assertIn("无需要升级的 SDK", result.stdout)
        self.assertNotIn("demo_project", result.stdout)

    def test_reports_only_first_three_unupgraded_sdks(self):
        self._write(
            self.target_sdk_root,
            "demo_project/demo_project.py",
            "print('same')\n",
        )
        self._write(
            self.reference_sdk_root,
            "demo_project/demo_project.py",
            "print('same')\n",
        )

        for name in ["sdk_a", "sdk_b", "sdk_c", "sdk_d"]:
            self._write(self.target_sdk_root, f"{name}/{name}.py", f"print('{name} current')\n")
            self._write(self.reference_sdk_root, f"{name}/{name}.py", f"print('{name} ref')\n")

        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("sdk_a", result.stdout)
        self.assertIn("sdk_b", result.stdout)
        self.assertIn("sdk_c", result.stdout)
        self.assertIn("还有 1 个未升级 SDK", result.stdout)
        self.assertNotIn("`sdk_d`", result.stdout)

    def test_unable_sdk_is_listed_but_not_treated_as_upgrade_target(self):
        self._write(
            self.target_sdk_root,
            "demo_project/demo_project.py",
            "print('same')\n",
        )
        self._write(
            self.reference_sdk_root,
            "demo_project/demo_project.py",
            "print('same')\n",
        )
        self._write(
            self.reference_sdk_root,
            "broken_sdk/broken_sdk.py",
            "print('ref main')\n",
        )
        (self.target_sdk_root / "broken_sdk").mkdir(parents=True, exist_ok=True)

        result = self._run()
        self.assertEqual(result.returncode, 0)
        self.assertIn("无需要升级的 SDK", result.stdout)
        self.assertIn("无法判断的 SDK", result.stdout)
        self.assertIn("broken_sdk", result.stdout)

    def test_missing_support_files_forces_upgrade_prompt(self):
        self._write(
            self.target_sdk_root,
            "partner_sdk/partner_sdk.py",
            "print('same')\n",
        )
        self._write(
            self.reference_sdk_root,
            "partner_sdk/partner_sdk.py",
            "print('same')\n",
        )
        self._write(self.reference_sdk_root, "partner_sdk/sdk_client.py", "client\n")
        self._write(self.reference_sdk_root, "partner_sdk/test_client.py", "test\n")

        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("partner_sdk", result.stdout)
        self.assertIn("sdk_client.py", result.stdout)
        self.assertIn("test_client.py", result.stdout)
        self.assertNotIn("无需要升级的 SDK", result.stdout)


if __name__ == "__main__":
    unittest.main()
