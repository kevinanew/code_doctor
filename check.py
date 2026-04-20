"""
# PRD: 全量代码检查工具 (Full Check Tool)

## 1. 目标
提供一个统一的入口点，通过 shell 调用自动运行当前目录下所有的代码检查脚本。这简化了执行流程，让用户可以通过一个命令运行所有检查项。

## 2. 检查规则
- **检测对象**：当前目录（脚本所在目录）下的所有 `.py` 文件。
- **排除范围**：
    - 脚本自身 (`check.py`)。
    - 所有以 `test_` 开头的测试脚本。
    - 隐藏文件和目录（以 `.` 开头）。
- **环境依赖**：
    - **必须安装 Git**：脚本依赖 Git 进行状态监控。
    - **必须在仓库内运行**：目标路径或其父级必须是一个有效的 Git 仓库。
- **执行逻辑**：
    - 启动时校验 Git 环境，失败则立即退出。
    - 遍历符合条件的脚本文件并运行。
    - 在每个脚本运行结束后，立即检查 Git 状态。
    - 如果发现文件变动，**必须立即停止后续检查**，并引导 AI Agent 进行规范的提交。

## 3. 命令行接口
- **用法**：`python check.py <target_directory>`
- **参数**：`<target_directory>` 是需要递归检查的目录路径。

## 4. 预期效果
- 自动发现所有检查工具。
- 顺序运行并显示每个工具的完整输出。
- 在所有检查完成后给出明确的总结报告。
- **中断机制**：确保任何自动化修复引发的变动都能及时被发现并以 PR 形式提交。
"""

import os
import sys
import subprocess

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
    寻找当前目录下所有的检查脚本（排除测试脚本和自身）。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    scripts = []
    
    for file in os.listdir(current_dir):
        if file.endswith('.py') and not file.startswith('.') and not file.startswith('test_'):
            if file != 'check.py':
                scripts.append(os.path.join(current_dir, file))
    
    return sorted(scripts)

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
    if len(sys.argv) != 2:
        print("用法: python check.py <target_directory>")
        sys.exit(1)

    # [核心校验]: 确保 Git 环境可用
    ensure_git_environment()

    target_dir = sys.argv[1]
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
            
            # 记录结果状态
            results.append((script_name, process.returncode == 0))
            
            # [核心逻辑]: 检查 Git 状态变动
            if is_git_modified():
                print("\n" + "!" * 40)
                print("[警告]: 检测到本地文件已被修改或自动修复。")
                print("-" * 40)
                print("[AI Agent 动作指引]:")
                print("1. **停止执行**：全量检查已中断，因为检测到了文件变动。")
                print("2. **创建分支**：请基于当前修改创建一个新的 Git 分支。")
                print("3. **提交代码**：在该新分支上提交您的修改。")
                print("4. **提交 PR**：在 GitHub 上针对此修改提交 Pull Request。")
                print("-" * 40)
                sys.exit(1)

            print("-" * 40)
            
        except Exception as e:
            print(f"运行脚本 {script_name} 时发生错误: {e}")
            results.append((script_name, False))

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
