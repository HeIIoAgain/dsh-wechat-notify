# dsh-wechat-notify 优化清单

> ⚠️ **这份清单和 `RELEASE-v1.0.0.md` 是给你自己看的工作材料，不要提交到仓库。**
> 该进仓库的只有 `.gitignore`、`.github/workflows/ci.yml`、`.github/ISSUE_TEMPLATE/config.yml`。

目标仓库：https://github.com/HeIIoAgain/dsh-wechat-notify

现状（2026-11-05 核实）：`topics: []`、无 `.gitignore`、无 `.github/`、`releases: []`、`tags: []`、只有 1 条 commit。
代码和测试本身很好（61 pytest + 11 Node 测试），**问题全在元数据和文档一致性**。

---

# P0 · 会让陌生人第一步就失败的（今天必须做）

## P0-1 替换 `OWNER` 占位符（3 个文件，别全局替换）

`OWNER` 出现在：`README.md`、`README.en.md`、`pyproject.toml`（`[project.urls]` 三处）。

**Windows PowerShell**（在仓库根目录执行）：

```powershell
foreach ($f in 'README.md','README.en.md','pyproject.toml') {
  $p = (Resolve-Path $f).Path
  $t = Get-Content -LiteralPath $p -Raw -Encoding UTF8
  $t = $t -replace 'github\.com/OWNER/dsh-wechat-notify','github.com/HeIIoAgain/dsh-wechat-notify'
  [System.IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($false)))
}
Select-String -Path README.md,README.en.md,pyproject.toml -Pattern 'OWNER'
```

最后那条命令**没有任何输出**才算替换干净。

**Git Bash / Linux / macOS**：

```bash
sed -i 's#github\.com/OWNER/dsh-wechat-notify#github.com/HeIIoAgain/dsh-wechat-notify#g' \
  README.md README.en.md pyproject.toml
grep -rn 'github\.com/OWNER' README.md README.en.md pyproject.toml || echo "已全部替换"
```

> ⚠️ **千万别用「整个仓库全局替换」**。`docs/publishing.md` 第 1 节的示例命令里**本身就写着
> `github.com/OWNER`**，那是教人替换用的模板，替换掉它反而把文档改坏了。

**验收**：打开 README，CI badge 指向 `HeIIoAgain`；`git clone` 命令能真的跑通。

## P0-2 补 `.gitignore`（安全项）

两份 README 都写着「`state/` 已被 git 忽略」，`docs/publishing.md` 写着「`.gitignore` 已覆盖」——
**但仓库里没有这个文件**。`state/credentials.json` 存的是 `bot_token`，等同机器人身份。

把 `wechat-publish/.gitignore` 拷进仓库根目录。

**验收**：

```bash
git status --short          # state/ 里的东西不该出现
git check-ignore -v state/credentials.json   # 应输出匹配的规则
```

## P0-3 补 CI（让 badge 不再骗人）

README 的 badge 指向 `.github/workflows/ci.yml`，但文件不存在 → badge 显示 `no status`。

把 `wechat-publish/.github/workflows/ci.yml` 拷进仓库。它跑四件事，全部是文档里已经承诺过的：

| 步骤 | 对应文档里的承诺 |
|---|---|
| `python tools/check_repo.py` | `docs/publishing.md` 第 0 节、README「目录结构」 |
| `python -m ruff check .` + `ruff format --check` | README「开发」 |
| `python -m pytest -q` | README「开发」、`docs/publishing.md` 第 0 节 |
| `node --test plugin/test/index.test.mjs` | README「开发」 |

**网页操作注意**：`Upload files` 拖拽会拒绝 `.github/workflows/` 下的文件，要用
**Add file ▾ → Create new file**，文件名直接输入 `.github/workflows/ci.yml`。

**验收**：Actions 页出现 `CI`，3 个 Python job + 2 个 Node job 全绿。

> 如果 `ruff format --check` 挂了：本地跑一次 `python -m ruff format .` 再提交，别改 CI。

## P0-4 补 `ISSUE_TEMPLATE/config.yml`

`docs/publishing.md` 提到这个文件，但它不存在。把 `wechat-publish/.github/ISSUE_TEMPLATE/config.yml` 拷进去，
它把安全问题上报到 Private vulnerability reporting，而不是公开 issue（`SECURITY.md` 就是这么写的）。

---

# P1 · 让人找得到、觉得靠谱（本周）

## P1-1 加 topics（现在 0 个）

```bash
gh repo edit HeIIoAgain/dsh-wechat-notify \
  --add-topic deepseek-harness,dsh-skill,dsh-plugin,wechat,wechat-bot,notifications,python,cli,openclaw
```

网页：About 旁 ⚙ → Topics → 每输入一个按回车 → Save。

依据：`deepseek-harness` 有 21,505 个仓库、`dsh-plugin` 有 26,258 个（都是活标签）；
`wechat-bot` / `notifications` 是大词，负责曝光；`python` / `cli` 是技术词。

> `openclaw` 是本项目依赖渠道的名字，可能很小众但精准，留着不亏。

## P1-2 打 tag + 建 Release（现在全空）

```bash
gh release create v1.0.0 \
  --title "v1.0.0 — 首个公开版本" \
  --notes-file wechat-publish/RELEASE-v1.0.0.md \
  --latest
```

或网页：Releases → Draft a new release → tag 输入 `v1.0.0` 选 *Create new tag on publish* →
正文粘贴 `RELEASE-v1.0.0.md` 全文 → 勾 Latest → Publish。

`pyproject.toml` 里 `version = "1.0.0"`，所以 tag 必须是 `v1.0.0`（`tests/test_version.py` 会校验版本一致）。

## P1-3 更新 `docs/publishing.md`

替换完 `OWNER` 之后，这份文档第 1 节「替换占位符」就过时了。两个选择：

- **省事**：在第 1 节开头加一行「✅ 已于 2026-11-05 完成，本节仅作记录」；
- **干净**：把第 1 节整段删掉。

同时第 3 节让你把 Description 设成英文——你已经设成中文了，顺手把这段改成实际值即可。

---

# P2 · 真正的体验优化（有空就做，收益最大）

## P2-1 发到 PyPI（名字已核实可用）

PyPI 上 `dsh-wechat-notify` **没人占用**（`GET pypi.org/pypi/dsh-wechat-notify/json` → 404），
而 `pyproject.toml` 已经写得很完整（`license-files`、classifiers、`[project.scripts]`、`package-dir`）。
`docs/publishing.md` 第 6 节就是这件事，只差执行：

```bash
python -m pip install build twine
python -m build
python -m twine upload dist/*        # 需要 PyPI 账号 + API token
```

发成功之后，README 的「方式二」可以从这行：

```bash
python -m pip install "git+https://github.com/HeIIoAgain/dsh-wechat-notify.git"
```

变成一行：

```bash
pip install dsh-wechat-notify
```

安装摩擦直接少一半，这是这个仓库最值得做的一件事。

推荐用 **Trusted Publishing**（PyPI 上配 GitHub OIDC）而不是长期 token：
仓库 Settings 里不用存任何密钥，`twine upload` 换成 `pypa/gh-action-pypi-publish`。

## P2-2 给上游依赖加上界

```toml
dependencies = [
  "wechat-openclaw-sdk>=0.1.0,<0.2",   # 现在只有 0.1.0 一个版本
  "qrcode[pil]>=8.0",
]
```

理由：`wechat-openclaw-sdk` 是第三方单人维护、目前**只有 0.1.0 一个版本**。它一旦发 0.2 改了协议，
`>=0.1.0` 会让你的用户自动升到不兼容版本，而你的代码零改动就坏了。加上界是零成本保险。

## P2-3 安装命令可以更短

README「方式一」现在是「clone 到任意目录 + 跑 install.ps1」。也可以像 airprint 那样直接给一行式：

```bash
git clone https://github.com/HeIIoAgain/dsh-wechat-notify.git ~/.dsh/skills/wechat-notify
```

（注意这条要求目标目录名必须是 `wechat-notify`，与 `SKILL.md` 的 name 一致。）

---

# 最终验收

- [ ] `grep -rn 'github.com/OWNER' README.md README.en.md pyproject.toml` 无输出
- [ ] `git check-ignore -v state/credentials.json` 有匹配
- [ ] Actions 页 `CI` 全绿（3 Python + 2 Node）
- [ ] About 显示 9 个 topics
- [ ] Releases 有 `v1.0.0`（Latest）
- [ ] 仓库里没有 `CHECKLIST.md` / `RELEASE-v1.0.0.md`
- [ ] README badge 显示 `CI passing`（不是 `no status`）
