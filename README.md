# Code Doctor

Code Doctor 是一个纯 Python 实现的代码质量检查工具集，旨在确保代码库符合特定的开发标准和最佳实践。

## 项目特点

- **零外部依赖**：本项目的所有工具仅依赖 Python 标准库（Standard Library），无需安装任何第三方类库。
- **单一职责**：每一个脚本只负责完成一个具体的检查功能。
- **自包含文档**：每一个脚本的头部 docstring 必须包含其对应的 PRD（需求文档）完整内容，方便快速查阅功能定义。
- **单文件逻辑**：一个脚本就是一个完整的功能实现及其需求定义，不依赖额外的 PRD 文件。
- **统一接口**：所有脚本都采用固定的用法，只接受一个参数，即需要检查的目录路径。

## 使用方法

所有的工具都通过以下方式调用：

```bash
python <script_name>.py <target_directory>
```

例如，运行 `meaningful_loop_variables.py`：

```bash
python meaningful_loop_variables.py /path/to/your/project
```

## 开发规范

1. **头部文档**：在 Python 脚本的开头，必须使用 `"""` 三引号包含该功能的 PRD 完整内容。
2. **标准库优先**：严禁引入 `requests`, `pandas`, `pydantic` 等外部依赖。
3. **参数处理**：脚本内部必须验证并仅处理一个目录路径参数。
4. **排除隐藏目录**：所有脚本在递归检查目录时，必须跳过以点（.）开头的隐藏目录（如 .git, .venv, .vscode 等）。
5. **自动化测试**：每一个脚本都必须配备相应的测试脚本（通常命名为 `test_<script_name>.py`），确保功能的准确性和稳定性。


