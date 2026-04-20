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
        print(f"[*] 开始扫描全局测试库...")

    # 1. 扫描全局，记录所有已经存在的 test_*.py 文件及其当前位置
    全局测试库 = {}
    for 根路径, 目录, 文件名列表 in os.walk("."):
        # 排除隐藏目录
        原来的目录 = list(目录)
        目录[:] = [目录名 for 目录名 in 目录 if not 目录名.startswith(".")]
        if verbose and len(原来的目录) != len(目录):
            已排除 = set(原来的目录) - set(目录)
            for 目录名 in 已排除:
                print(f"    - 跳过隐藏目录: {os.path.join(根路径, 目录名)}")

        for 文件 in 文件名列表:
            if 文件.startswith("test_") and 文件.endswith(".py"):
                # 记录发现的测试文件位置
                全局测试库[文件] = os.path.join(根路径, 文件)

    if verbose:
        print(f"[*] 已建立全局测试库，共记录 {len(全局测试库)} 个测试文件。")

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
        print("该目录下所有已发现的测试文件均已与其源代码同级。")
        sys.exit(0)
    else:
        print(f"[归位检查]: 发现位置错误的测试文件 (目录: {目标目录})")
        print("\n[AI Agent 动作指引]:")
        print("【重要】：请核实并归位以下测试文件：")

        for 归位项 in 需要归位列表:
            print(f"🔍 针对 '{归位项['源文件']}'：")
            print(
                f"   1. 核实：在 '{归位项['当前现有位置']}' 发现了疑似测试，请 `read_file` 核实内容。"
            )
            print(
                f"   2. 归位：如果匹配，移动文件到 '{归位项['归位目标']}' 并适配 import。"
            )
            print(
                f"   3. 占位：如果不匹配（误报），请在 '{归位项['归位目标']}' 创建仅包含一行注释的文件："
            )
            print("      `# 为避免归位误报自动生成的占位测试`")

        print(f"\n处理完毕后，请重新验证：`uv run 测试文件归位工具.py {目标目录}`")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试文件归位工具")
    parser.add_argument("目录", help="要整理的源代码目录")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细检查详情")
    
    args = parser.parse_args()
    执行归位检查(args.目录, args.verbose)
