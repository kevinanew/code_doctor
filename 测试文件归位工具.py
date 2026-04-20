"""
# 需求文档: 测试文件归位工具 (代码测试同目录化)

## 1. 目标
强制要求项目中所有**已经存在**的单元测试文件必须与其对应的源代码文件存放在**同一个目录**下。

本工具用于扫描指定目录，发现那些“身首异处”的测试文件，并引导 AI Agent 将其“归位”。通过让测试与代码 Side-by-Side，利用物理位置的唯一性解决通用文件名（如 `views.py`）导致的全局匹配冲突。

## 2. 归位规则
*   **归位目标**：源代码 `path/to/文件名.py` 对应的测试必须位于 `path/to/test_文件名.py`。
*   **寻找来源**：工具会在目标目录下全局搜索名为 `test_文件名.py` 的文件。
*   **归位执行规范**：
    *   **零代码侵入**：严禁修改任何 `.py` 源代码文件。
    *   **仅移动位置**：归位操作应仅通过 `git mv` 改变文件物理位置。严禁随意修改测试文件内容。
    *   **告知原因**：如果 AI Agent 判定确实需要修改文件内容（如适配极少数 import），则**必须在执行修改操作前，明确告知修改的具体原因及必要性**。
    *   **强制使用 Git**：AI Agent **必须且仅能**使用 `git mv` 命令执行归位操作。
    *   **严禁使用 rm**：严禁使用 `rm` 或 `rm -rf` 删除任何测试文件或旧的测试目录（如 `unittests`）。
    *   **无需清理空目录**：在所有文件归位完成后，**无需**处理产生的空目录，也**严禁**执行 `git clean`。因为 GitHub 不会记录空目录，本地残留空目录无影响。
    *   **忽略特殊文件**：空的 `__init__.py` 文件不属于本工具的归位范围，不做任何处理。

*   **核实与占位逻辑**：
    *   AI Agent 发现全局存在同名测试时，必须核实其内容。
    *   **匹配**：执行归位（移动并适配）。
    *   **不匹配 (误报)**：AI Agent 必须在源代码同级目录创建一个**本地占位测试文件**。
*   **占位文件规范**：
    *   文件名：`test_文件名.py`。
    *   内容：**严禁编写任何 import 或测试逻辑**。仅允许包含一行注释：`# 为避免归位误报自动生成的占位测试`。
    *   作用：通过物理文件的存在，使工具在下次运行时判定该文件“已对齐”，从而彻底消除该条误报。

## 3. 使用方法
```bash
uv run 测试文件归位工具.py <要整理的源代码目录> [--verbose]
```

## 4. 输出规范
### 4.1 状态 A: 已对齐 (成功)
*   **提示**: "[归位检查]: 成功。该目录下所有已发现的测试文件均已与其源代码同级。"

### 4.2 状态 B: 未对齐 (需要归位)
*   **提示**: "[归位检查]: 发现位置错误的测试文件。"
*   **动作指引**: 告知当前位置并要求使用 `git mv` 移动。
"""

import os
import sys
import argparse

# 关键配置
排除关键字 = ["__pycache__", "migrations", "unittest", "unittests", "tests"]
排除文件名 = ["__init__.py", "conftest.py"]


def 执行归位检查(目标目录, verbose=False):
    """检查并指引位置错误的测试文件归位"""
    需要归位列表 = []

    if verbose:
        print(f"[*] 开始扫描全局测试库 (范围: {目标目录})...")

    # 1. 扫描目标目录，记录所有已经存在的 test_*.py 文件及其当前位置
    全局测试库 = {}
    
    for 根路径, 目录, 文件名列表 in os.walk(目标目录):
        # 排除隐藏目录
        原来的目录 = list(目录)
        目录[:] = [目录名 for 目录名 in 目录 if not 目录名.startswith(".")]
        if verbose and len(原来的目录) != len(目录):
            已排除 = set(原来的目录) - set(目录)
            for 目录名 in 已排除:
                print(f"    - 跳过隐藏目录: {os.path.join(根路径, 目录名)}")

        for 文件 in 文件名列表:
            # 记录测试文件
            if 文件.startswith("test_") and 文件.endswith(".py"):
                全局测试库[文件] = os.path.join(根路径, 文件)

    if verbose:
        print(f"[*] 已建立全局库，记录了 {len(全局测试库)} 个测试文件。")

    # 2. 检查目标目录下的源代码
    if not os.path.exists(目标目录):
        print(f"[错误]: 目标目录不存在: {目标目录}")
        sys.exit(1)

    if verbose:
        print(f"[*] 开始检查目录: {目标目录}")

    for 根目录, 目录列表, 文件列表 in os.walk(目标目录):
        # 排除隐藏目录
        原来的目录 = list(目录列表)
        目录列表[:] = [目录名 for 目录名 in 目录列表 if not 目录名.startswith(".")]
        if verbose and len(原来的目录) != len(目录列表):
            已排除 = set(原来的目录) - set(目录列表)
            for 目录名 in 已排除:
                print(f"    - 跳过隐藏目录: {os.path.join(根目录, 目录名)}")

        # 过滤掉已有的测试目录，避免自检
        if any(关键字 in 根目录 for 关键字 in 排除关键字):
            if verbose:
                print(f"    - 跳过排除目录: {根目录}")
            continue

        # 过滤掉排除关键字目录
        原来的目录 = list(目录列表)
        目录列表[:] = [目 for 目 in 目录列表 if not any(关键字 in 目 for 关键字 in 排除关键字)]
        if verbose and len(原来的目录) != len(目录列表):
            已排除 = set(原来的目录) - set(目录列表)
            for 目录名 in 已排除:
                print(f"    - 跳过排除目录: {os.path.join(根目录, 目录名)}")

        for 文件 in 文件列表:
            if not 文件.endswith(".py") or 文件 in 排除文件名:
                if verbose and 文件.endswith(".py"):
                    print(f"    - 跳过排除文件: {os.path.join(根目录, 文件)}")
                continue

            # 如果本身就是 test_ 开头，且在目标目录内，通常是已对齐或待移动的目标，跳过对它的“归位检查”
            if 文件.startswith("test_"):
                if verbose:
                    print(f"    - 发现测试文件 (跳过归位检查): {os.path.join(根目录, 文件)}")
                continue

            源文件路径 = os.path.join(根目录, 文件)
            预期测试名 = f"test_{文件}"
            理想测试路径 = os.path.join(根目录, 预期测试名)

            if verbose:
                print(f"    [检查]: {源文件路径}")

            # 检查：测试文件是否已经在理想位置
            if not os.path.exists(理想测试路径):
                # 如果不在，去全局库里找找
                现有位置 = 全局测试库.get(预期测试名)
                # 核心逻辑：只有找到了身在别处的测试，才需要归位；如果到处都找不到，则忽略。
                if 现有位置:
                    if verbose:
                        print(f"      [!] 发现测试偏移: {现有位置}")
                    需要归位列表.append(
                        {
                            "源文件": 源文件路径,
                            "归位目标": 理想测试路径,
                            "当前现有位置": 现有位置,
                        }
                    )
                else:
                    if verbose:
                        print(f"      [OK] 未发现对应测试文件，无需归位。")
            else:
                if verbose:
                    print(f"      [OK] 测试文件已在理想位置: {理想测试路径}")

    # 3. 输出报告
    if not 需要归位列表:
        print(f"[归位检查]: 成功 (目录: {目标目录})")
        print("该目录下所有已发现的测试文件均已正确归位。")
        sys.exit(0)
    else:
        print(f"[归位检查]: 发现位置错误的测试文件 (目录: {目标目录})")
        print("\n[AI Agent 动作指引]:")
        
        if 需要归位列表:
            print("【测试文件归位】：")
            for 归位项 in 需要归位列表:
                print(f"🔍 针对 '{归位项['源文件']}'：")
                print(
                    f"   1. 核实：在 '{归位项['当前现有位置']}' 发现了疑似测试，请 `read_file` 核实内容。"
                )
                print(
                    f"   2. 归位：如果匹配，**必须使用 `git mv`** 移动文件到 '{归位项['归位目标']}'。"
                )
                print(
                    "      **注意**：严禁随意修改内容。若判定必须修改（如适配 import），**务必先告知修改原因**。"
                )
                print(
                    f"   3. 占位：如果不匹配（误报），请在 '{归位项['归位目标']}' 创建仅包含一行注释的文件："
                )
                print("      `# 为避免归位误报自动生成的占位测试`")

        print("\n【清理与特殊说明】：")
        print("1. **严禁修改源码**：绝对禁止修改任何 `.py` 源代码文件。")
        print("2. **修改须说明原因**：若确实需要修改测试/配置文件内容，**必须在操作前明确告知原因**。")
        print("3. **严禁使用 mv/rm**：必须使用 `git mv` 移动位置，禁止使用 `rm` 删除旧目录。")
        print("4. **内容零改动**：应优先仅移动物理位置。通常不需要修改 `import`，尽量保持文件内容不变。")
        print("5. **无需清理空目录**：无需运行 `git clean`，空目录留在本地无碍。")
        print("6. **空的 __init__.py**：请直接忽略。")

        print(f"\n处理完毕后，请重新验证：`uv run 测试文件归位工具.py {目标目录}`")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试文件归位工具")
    parser.add_argument("目录", help="要整理的源代码目录")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细检查详情")
    
    args = parser.parse_args()
    执行归位检查(args.目录, args.verbose)
