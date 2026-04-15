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
- **执行逻辑**：
    - 遍历符合条件的脚本文件。
    - 直接通过 shell 运行每个脚本，并将目标目录（命令行参数）传递给它们。
    - 捕获并汇总每个检查脚本的输出。
- **结果输出**：打印每个检查工具的运行结果，最后显示汇总统计信息。

## 3. 命令行接口
- **用法**：`python check.py <target_directory>`
- **参数**：`<target_directory>` 是需要递归检查的目录路径。

## 4. 预期效果
- 自动发现所有检查工具。
- 顺序运行并显示每个工具的完整输出。
- 在所有检查完成后给出明确的总结报告。
"""

import os
import sys
import subprocess

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

def main():
    if len(sys.argv) != 2:
        print("用法: python check.py <target_directory>")
        sys.exit(1)

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
            # 使用 shell=True 直接调用 shell 运行脚本
            command = f'python3 "{script}" "{target_dir}"'
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True
            )
            
            print(process.stdout)
            if process.stderr:
                print(f"错误输出:\n{process.stderr}")
            
            # 记录结果状态
            results.append((script_name, process.returncode == 0))
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
