# 发布到 GitHub

> ✅ **已于 2026-11-05 完成。** 仓库已公开发布、CI 全绿、tag `v1.0.0` 与 Release 均已就位，
> 第 1 节「替换占位符」与第 2 节「创建仓库并推送」现在只是历史记录，**不要再照着执行**——
> 再替换一次会把已经正确的 `HeIIoAgain` URL 改坏。
>
> 本文档仍有价值的部分：**第 6 节 PyPI 发布**（尚未做）。

这个仓库已经是"可直接上架"的状态：代码、测试、CI、文档、许可证都齐了。下面是把它推到
GitHub 并打出第一个 release 的清单。

> 需要 Git：`git --version` 能跑就跳过这一步，否则先装
> `winget install Git.Git`（或 <https://git-scm.com/downloads>）。
> 完全不装 Git 也可以走图形界面：用 GitHub Desktop（Add local repository → create → Publish），
> 或直接在 GitHub 网页上新建仓库并拖拽上传整个文件夹。

## 0. 上架前自检（30 秒）

```bash
python tools/check_repo.py     # 无密钥、无个人绝对路径、无 runtime state
python -m pytest -q            # 61 passed
node --test plugin/test/index.test.mjs
```

确认 `scripts/state/`、`credentials.json`、`qr.png` **没有**被提交（`.gitignore` 已覆盖）。

## 1. 替换占位符

仓库里所有指向自己的 URL 都写成 `OWNER`，第一次提交前全局替换成你的 GitHub 用户名或组织名：

```bash
# Linux / macOS
grep -rl 'github.com/OWNER' . --exclude-dir=.git | xargs sed -i 's#github.com/OWNER#github.com/<你的名字>#g'
```

```powershell
# Windows PowerShell
Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notmatch '\\\.git\\' } |
  ForEach-Object {
    $t = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8
    if ($t -match 'github\.com/OWNER') {
      [System.IO.File]::WriteAllText($_.FullName, ($t -replace 'github\.com/OWNER', 'github.com/<你的名字>'), (New-Object System.Text.UTF8Encoding($false)))
    }
  }
```

涉及文件：`README.md`、`README.en.md`、`pyproject.toml`、`.github/ISSUE_TEMPLATE/config.yml`。
`OWNER` 出现在 CI badge、`[project.urls]`、安全公告链接里。

## 2. 初始化并推送

```bash
git init -b main
git add -A
git commit -m "feat: initial public release of dsh-wechat-notify"
git remote add origin git@github.com:<你的名字>/dsh-wechat-notify.git
git push -u origin main
```

推送前再看一眼暂存区，确保没有 `state/`：

```bash
git status --short
git ls-files | grep -i -E 'state/|credentials|qr\.png' || echo "clean"
```

## 3. 仓库设置（网页上点几下）

- **Description**：`On-demand WeChat notifications for DeepSeek Harness (DSH) agents.`
- **Topics**：`dsh` `deepseek-harness` `wechat` `wechat-bot` `notifications` `python` `skill`
- **Actions**：确认 workflow 已启用（首次 push 后 CI 会自动跑 Python 矩阵、Node 测试、
  安装器测试、仓库卫生检查）。
- **Security**：开启 *Private vulnerability reporting*（`SECURITY.md` 里指向它）。
- **Branch protection**（可选）：要求 `CI` 全绿再合并。

## 4. 打第一个 release

```bash
git tag -a v1.0.0 -m "dsh-wechat-notify v1.0.0"
git push origin v1.0.0
```

在 GitHub 上 *Releases → Draft a new release*，选 `v1.0.0`，标题 `v1.0.0`，正文直接贴
`CHANGELOG.md` 里 `## [1.0.0]` 那一节。

## 5. 发版流程（以后）

1. 改 `pyproject.toml` 的 `version` 和 `src/wechat_notify/config.py` 的 `__version__`
   （`tests/test_version.py` 会强制两者一致），
2. 在 `CHANGELOG.md` 顶部加 `## [x.y.z]` 小节，
3. 提交、打 tag、发 release。

## 6.（可选）发到 PyPI

```bash
python -m pip install build twine
python -m build
python -m twine upload dist/*
```

包名 `dsh-wechat-notify`，`pip install dsh-wechat-notify` 即可获得 `wechat-notify` 命令。
发 PyPI 前把 `[project.urls]` 的 `Homepage` 改成真实仓库地址。

## 7. 上架后

- 更新 DSH 技能：`bash install.sh --force` 或 `.\install.ps1 -Force`（`scripts/state` 会保留）。
- 别人怎么用：`README.md` 的"安装"三种方式都可用；技能用户只需要 `install.ps1` / `install.sh`。
