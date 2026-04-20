"""
# PRD (开发规范引用)
请在阅读本脚本具体功能前，务必先查看并遵守 `PRD_COMMON.md` 中的“通用开发规范”。

# 脚本具体 PRD: 全量代码检查工具 (Full Check Tool)
...
## 1. 目标
提供一个统一的入口点，通过 shell 调用自动运行当前目录下所有的代码检查脚本。这简化了执行流程，让用户可以通过一个命令运行所有检查项。

## 2. 检查规则
- **检测对象**：当前目录（脚本所在目录）下的所有 `.py` 文件。
- **排除范围**：
    - 脚本自身 (`check.py`)。
    - 所有以 `test_` 开头的测试脚本。
- **环境依赖**：
    - **必须安装 Git**：脚本依赖 Git 进行状态监控。
    - **必须在仓库内运行**：目标路径或其父级必须是一个有效的 Git 仓库。
- **执行逻辑**：
    - **参数解析**：支持 0 或 1 个参数。如果没有提供参数，默认检查当前目录。
    - **按顺序运行**：优先运行 `开发环境删除工具.py`，然后是 `配置文件归位工具.py`，接着是 `测试文件归位工具.py`，其余工具按字母顺序运行。
    - 启动时校验 Git 环境，失败则立即退出。
    - **快速失败**：如果任何检查脚本运行失败（返回非零退出码），立即停止执行后续脚本并引导 AI Agent 在新分支提交 PR。
    - 在每个脚本运行结束后，立即检查 Git 状态。
    - **变更中断**：如果发现文件变动，必须立即停止后续检查，并引导 AI Agent 在新分支提交 PR，且不再进行本地检查。
- **结果输出**：打印每个检查工具的运行结果，全部完成后显示汇总统计信息。

## 3. 命令行接口
- **用法**：`python check.py [target_directory]`
- **参数**：`[target_directory]` 是需要递归检查的目录路径（可选，默认为当前目录 `.`）。

## 4. 预期效果

- 自动发现所有检查工具并按优先级排序执行。
- 顺序运行并显示每个工具的完整输出。
- 中断机制确保自动修复引发的变动能及时被发现，并规范 Agent 的提交行为。
"""

import os
import sys
import subprocess

# 优先级脚本列表（按顺序排列）
PRIORITY_SCRIPTS = ["开发环境删除工具.py", "配置文件归位工具.py", "测试文件归位工具.py"]

def ensure_git_environment():
    """
    确保系统安装了 Git 且当前目录处于 Git 仓库中。
    """
    try:
        # 1. 检查 git 是否安装
        subprocess.run(['git', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[错误]: 未发现可用的 'git' 命令。请确保系统已安装 Git 并且已将其加入 PATH。")
        sys.exit(1)

    try:
        # 2. 检查当前是否处于 Git 仓库中
        result = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], capture_output=True, text=True)
        if result.returncode != 0 or "true" not in result.stdout.lower():
            print("[错误]: 当前目录不是一个有效的 Git 仓库。全量检查工具必须在 Git 仓库内运行。")
            sys.exit(1)
    except Exception as e:
        print(f"[错误]: 校验 Git 仓库状态时发生异常: {e}")
        sys.exit(1)

def find_check_scripts():
    """
    寻找当前目录下所有的检查脚本，并按优先级排序。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    all_files = os.listdir(current_dir)
    
    # 筛选出符合条件的脚本名
    check_files = [
        f for f in all_files 
        if f.endswith('.py') and not f.startswith('.') and not f.startswith('test_') and f != 'check.py'
    ]
    
    # 按照优先级排序
    priority = []
    others = []
    
    # 首先提取优先级脚本
    for p_script in PRIORITY_SCRIPTS:
        if p_script in check_files:
            priority.append(os.path.join(current_dir, p_script))
            check_files.remove(p_script)
            
    # 其余脚本按字母顺序排序
    for other_script in sorted(check_files):
        others.append(os.path.join(current_dir, other_script))
        
    return priority + others

def is_git_modified():
    """
    检查 Git 工作区是否有变动（已修改或已暂存的文件）。
    """
    # --porcelain 产生易于解析的输出，如果有变动则输出非空
    result = subprocess.run(
        ['git', 'status', '--porcelain'],
        capture_output=True,
        text=True
    )
    return bool(result.stdout.strip())

def main():
    # 参数解析：支持可选的目标目录，默认为当前目录
    if len(sys.argv) > 2:
        print("用法: python check.py [target_directory]")
        sys.exit(1)

    target_dir = sys.argv[1] if len(sys.argv) == 2 else "."
    
    # [核心校验]: 确保 Git 环境可用
    ensure_git_environment()

    if not os.path.isdir(target_dir):
        print(f"错误: '{target_dir}' 不是一个有效的目录。")
        sys.exit(1)

    scripts = find_check_scripts()
    if not scripts:
        print("未发现可用的检查脚本。")
        return

    print(f"=== 开始全量检查，目标目录: {target_dir} ===\n")
    
    results = []
    for script in scripts:
        script_name = os.path.basename(script)
        print(f"正在运行 {script_name}...")
        
        try:
            # 运行脚本，将目标目录作为参数传递
            process = subprocess.run(
                ['python3', script, target_dir],
                capture_output=True,
                text=True
            )
            
            print(process.stdout)
            if process.stderr:
                print(f"错误输出:\n{process.stderr}")
            
            if process.returncode != 0:
                print(f"\n错误: {script_name} 检查失败，停止后续检查。")
                print("-" * 40)
                print("[AI Agent 动作指引]:")
                print(f"1. **修复问题**：请根据上述错误输出修复 {script_name} 发现的问题。")
                print("2. **创建分支/提交 PR**：修复后请在新的 Git 分支上提交代码并创建 PR。")
                print("3. **不要本地检查**：不要在本地重新运行 check.py，直接提交以触发 CI 检查。")
                print("最后，请使用中文回答。")
                print("-" * 40)
                sys.exit(1)
            
            # 记录结果状态
            results.append((script_name, True))
            
            # [核心逻辑]: 检查 Git 状态变动
            if is_git_modified():
                print("\n" + "!" * 40)
                print("[警告]: 检测到本地文件已被修改或自动修复。")
                print("-" * 40)
                print("[AI Agent 动作指引]:")
                print("1. **停止执行**：全量检查已中断，因为检测到了文件变动。")
                print("2. **创建分支/提交 PR**：请基于当前修改创建一个新的 Git 分支并提交 PR。")
                print("3. **不要本地检查**：不要在本地继续运行 check.py，直接提交以触发 CI 检查。")
                print("最后，请使用中文回答。")
                print("-" * 40)
                sys.exit(1)

            print("-" * 40)
            
        except Exception as e:
            print(f"运行脚本 {script_name} 时发生错误: {e}")
            sys.exit(1)

    print("\n=== 全量检查总结报告 ===")
    all_passed = True
    for name, success in results:
        status = "通过" if success else "失败"
        print(f"  - {name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n恭喜！所有代码检查项均已通过。")
    else:
        print("\n注意：部分代码检查项未通过，请根据上述详细报告进行修改。")
        sys.exit(1)

if __name__ == "__main__":
    main()
