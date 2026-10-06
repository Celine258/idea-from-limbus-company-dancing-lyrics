# 项目协作规则

本文件适用于“跳动的歌词”项目目录及其所有子目录。

## 1. 每次改动必须提交 commit

- 每次完成一项逻辑完整的改动后，都必须提交一个 Git commit，便于追踪和回滚。
- 提交信息应清楚说明改动内容和目的；同一提交中的文件应属于同一项改动。
- 完成测试、验证和变更记录后再提交，交付时提供 commit 编号和验证结果。

## 2. 每次改动必须编写或更新测试

- 每次改动后，都必须编写或更新相关测试，覆盖此次新增行为、修复问题或规则要求。
- 代码、配置、启动脚本及文档改动都适用此要求；文档改动需要相应的文档校验。
- 交付给用户之前，必须确保所有测试和验证全部通过。测试失败时先修复问题，再重新运行相关检查。
- 验证范围应与改动对应：运行全部自动测试；涉及桌面启动、音频或歌词动画时，还需运行 Windows 集成验证并检查相关实际行为。

## 3. 每次改动必须留下记录

- 每次改动都必须新增或更新 [CHANGELOG.md](CHANGELOG.md) 中的条目。
- 记录日期、改动目的、涉及文件、测试和验证命令、实际结果，以及影响或已知限制。
- 记录内容必须与实际完成的改动和验证一致，并与相关代码、测试放入同一个 commit。

## 执行顺序

1. 检查现有代码、项目规则和 Git 状态，确定改动范围。
2. 实施改动，并编写或更新相关测试。
3. 运行全部自动测试以及与此次改动相关的验证，修复发现的问题。
4. 更新 `CHANGELOG.md`，记录实际验证结果。
5. 检查最终 diff、文件范围和空白错误，提交 Git commit。
6. 交付改动说明、验证结果和 commit 编号。

## 验证命令

在项目根目录运行全部自动测试，包含 [核心功能测试](tests/test_core.py) 和 [协作文档校验](tests/test_workflow_docs.py)：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

涉及桌面启动、音乐播放或歌词动画时，额外运行静音集成验证；结果保存在 `artifacts`：

```powershell
.\.venv\Scripts\python.exe main.py --smoke
```

涉及启动脚本或打包版本时，还需从实际启动入口验证控制面板的 Windows 原生可见性：

```powershell
.\启动.bat -Smoke -ReportDirectory "$PWD\artifacts\launcher-bat"
```

提交前检查暂存区：

```powershell
git diff --cached --check
git diff --cached --stat
```
