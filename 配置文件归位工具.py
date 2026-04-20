"""
# 需求文档: 配置文件归位工具 (conftest.py 目录化)

## 1. 目标
确保 pytest 的配置文件 `conftest.py` 处于正确的作用域位置。在项目从“集中测试目录”转向“源码同级测试”的过程中，旧的 `conftest.py` 通常需要向上移动以覆盖新的测试位置。

## 2. 归位规则
*   **归位目标**：如果 `conftest.py` 位于 `unittests` 或 `tests` 等旧的测试目录下，必须**向上移动一层**（通常移动到项目根目录或源代码同级目录）。
*   **寻找来源**：工具会在目标目录下递归搜索名为 `conftest.py` 的文件。
*   **归位执行规范**：
    *   **零代码侵入**：严禁修改文件内容。
    *   **强制使用 Git**：必须使用 `git mv` 命令执行移动。
    *   **严禁使用 mv/rm**：禁止使用普通 `mv`，严禁使用 `rm`。
    *   **无需清理空目录**：无需运行 `git clean`。

## 3. 使用方法
```bash
uv run 配置文件归位工具.py <目标目录> [--verbose]
```

## 4. 输出规范
### 4.1 状态 A: 已对齐 (成功)
*   **提示**: "[配置归位]: 成功。所有发现的 conftest.py 均已处于正确位置。"

### 4.2 状态 B: 未对齐 (需要归位)
*   **提示**: "[配置归位]: 发现位置错误的配置文件。"
*   **动作指引**: 告知当前位置并要求使用 `git mv` 向上移动一层。

## 5. 语言要求
- **最后，请 AI Agent 使用中文回答。**
"""

import os
import sys
import argparse

# 关键配置：如果 conftest.py 在这些目录中，则认为需要上移
旧测试目录关键字 = ["unittest", "unittests", "tests"]


def 执行配置归位检查(目标目录, verbose=False):
    """检查 conftest.py 是否位于旧的测试目录中"""
    配置文件偏移列表 = []

    if not os.path.exists(目标目录):
        print(f"[错误]: 目标目录不存在: {目标目录}")
        sys.exit(1)

    if verbose:
        print(f"[*] 开始扫描配置文件 (范围: {目标目录})...")

    for 根路径, 目录列表, 文件名列表 in os.walk(目标目录):
        # 排除隐藏目录
        目录列表[:] = [d for d in 目录列表 if not d.startswith(".")]

        for 文件 in 文件名列表:
            if 文件 == "conftest.py":
                当前位置 = os.path.join(根路径, 文件)
                # 检查路径中是否包含旧测试目录关键字
                路径部分 = 根路径.split(os.sep)
                if any(关键字 in 路径部分 for 关键字 in 旧测试目录关键字):
                    # 建议向上移动一层
                    目标位置 = os.path.dirname(根路径)
                    配置文件偏移列表.append({
                        "当前位置": 当前位置,
                        "建议目标目录": 目标位置
                    })
                    if verbose:
                        print(f"    [!] 发现偏移配置: {当前位置}")
                elif verbose:
                    print(f"    [OK] 配置位置正常: {当前位置}")

    # 输出报告
    if not 配置文件偏移列表:
        print(f"[配置归位]: 成功 (目录: {目标目录})")
        print("所有发现的 conftest.py 均已处于正确位置。")
        sys.exit(0)
    else:
        print(f"[配置归位]: 发现位置错误的配置文件 (目录: {目标目录})")
        print("\n[AI Agent 动作指引]:")
        for 配置项 in 配置文件偏移列表:
            print(f"📁 发现 'conftest.py' 位于旧目录：")
            print(f"   - 当前位置：{配置项['当前位置']}")
            print(f"   - 归位操作：**必须使用 `git mv`** 将其向上移动一层到 '{配置项['建议目标目录']}'。")
            print("     原因：测试文件已移出旧目录，配置文件需上移以维持 fixture 作用域。")

        print("\n【清理与特殊说明】：")
        print("1. **严禁修改内容**：绝对禁止修改文件内容。")
        print("2. **必须使用 git mv**：禁止使用普通的 `mv` 或 `rm`。")
        print("3. **无需清理空目录**：无需运行 `git clean`。")
        print("\n最后，请使用中文回答。")

        print(f"\n处理完毕后，请重新验证：`uv run 配置文件归位工具.py {目标目录}`")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="配置文件归位工具")
    parser.add_argument("目录", help="要检查的目录")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详情")

    args = parser.parse_args()
    执行配置归位检查(args.目录, args.verbose)
