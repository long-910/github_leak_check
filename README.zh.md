# github-leak-check

**Language / 语言 / 言語:** [English](README.md) | 中文 | [日本語](README.ja.md)

扫描 GitHub 提交记录、文件内容和用户资料中的非 `noreply` 邮件地址，并将结果以动态徽章的形式展示在你的 GitHub 主页上。

<!-- 状态卡片 — 由 GitHub Actions 每日自动更新 -->
<!-- 将 USERNAME 替换为你的 GitHub 用户名后取消注释 -->
<!-- ![扫描状态](https://raw.githubusercontent.com/USERNAME/github_leak_check/main/results/card.svg) -->

---

## 功能说明

1. **提交记录扫描** — 检查你所有仓库中每条提交的 `author.email` 和 `committer.email`
2. **文件内容扫描** — 在 README、package.json、pyproject.toml 等文件中搜索邮件地址模式
3. **资料页扫描** — 检查你的 GitHub 公开资料是否设置了邮件地址
4. 将所有非 `@users.noreply.github.com`（及其他 bot/noreply）地址标记为潜在泄露
5. **增量扫描** — 重复运行时，仅检查上次扫描时间戳之后的新提交
6. **默认排除 Fork 仓库** — 除非指定 `--include-forks`，否则跳过所有 Fork 的仓库

输出文件说明：
- `results/summary.json` — 汇总统计，**不含真实邮件地址**（会提交到仓库）；含 `since` 字段，记录本次扫描的起始时间
- `results/card.svg` — 用于嵌入展示的状态卡片（会提交到仓库）
- `results/leaks.json` — 包含真实地址的完整详情（**已加入 .gitignore，绝不提交**）

---

## 配置步骤

### 1. Fork 本仓库

Fork 到你自己的账号，这样 GitHub Actions 将以你的身份运行。

### 2. 创建 Personal Access Token

前往 **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens**，创建具有以下权限的 Token：

| 权限 | 访问级别 |
|---|---|
| **Contents** | Read-only（所有仓库） |
| **Metadata** | Read-only |
| **Email addresses** | Read-only（Account permissions 下） |

> 经典 PAT 也可用：勾选 `repo` + `read:user` 权限。

### 3. 将密钥添加到仓库

在你的 Fork 中：**Settings → Secrets and variables → Actions → New repository secret**

| 密钥名称 | 是否必填 | 值 |
|---|---|---|
| `GH_PAT` | 必填 | 第 2 步创建的 Token |
| `TARGET_EMAILS` | 选填 | 要监测的邮件地址（逗号分隔），例如 `you@work.com,old@isp.net` |

若未设置 `TARGET_EMAILS`，扫描器会标记仓库中**所有**非 noreply 邮件地址。
若已设置，则只报告这些特定地址的泄露情况。

### 4. 启用 Actions

前往 Fork 的 **Actions** 标签页，按提示启用工作流。
扫描将在每天 03:00 UTC 及每次推送到 `main` 分支时自动执行。
也可在 Actions 标签页手动触发。

### 5. 在 Profile README 中嵌入状态卡片

在你的 `USERNAME/USERNAME` 主页仓库的 README 中添加以下内容：

```markdown
![邮件泄露扫描](https://raw.githubusercontent.com/USERNAME/github_leak_check/main/results/card.svg)
```

将 `USERNAME` 替换为你的 GitHub 用户名。

---

## 本地运行

首先安装依赖：

```bash
pip install -r requirements.txt
```

### macOS / Linux

```bash
# 仅扫描上次检查后的新提交（默认行为——自动读取 summary.json 中的时间戳）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --verbose

# 强制全量扫描（忽略上次扫描时间）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --full

# 从指定日期起扫描
GH_PAT=ghp_... python scan.py YOUR_USERNAME --since 2026-01-01T00:00:00Z

# 同时扫描 Fork 的仓库（默认排除）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --include-forks

# 只检测指定邮件地址
GH_PAT=ghp_... python scan.py YOUR_USERNAME --email your@example.com

# 同时检测多个地址
GH_PAT=ghp_... python scan.py YOUR_USERNAME --email work@example.com --email personal@example.com

# 从已有摘要生成卡片
python generate_card.py

# 跳过文件内容扫描（更快）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --no-files

# 增加每仓库的提交扫描深度（默认：500）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --max-commits 2000
```

### Windows — PowerShell

```powershell
$env:GH_PAT = "ghp_..."

# 仅扫描上次检查后的新提交（默认）
python scan.py YOUR_USERNAME --verbose

# 强制全量扫描
python scan.py YOUR_USERNAME --full

# 从指定日期起扫描
python scan.py YOUR_USERNAME --since 2026-01-01T00:00:00Z

# 同时扫描 Fork 的仓库
python scan.py YOUR_USERNAME --include-forks

# 只检测指定邮件地址
python scan.py YOUR_USERNAME --email your@example.com

# 同时检测多个地址
python scan.py YOUR_USERNAME --email work@example.com --email personal@example.com

# 生成卡片
python generate_card.py

# 跳过文件内容扫描（更快）
python scan.py YOUR_USERNAME --no-files

# 增加提交扫描深度
python scan.py YOUR_USERNAME --max-commits 2000
```

### Windows — 命令提示符（cmd.exe）

```cmd
set GH_PAT=ghp_...

REM 仅扫描上次检查后的新提交（默认）
python scan.py YOUR_USERNAME --verbose

REM 强制全量扫描
python scan.py YOUR_USERNAME --full

python generate_card.py
```

---

## 修复泄露

运行 `scan.py` 后，使用 `fix.py` 替换泄露的邮件地址。

```bash
python fix.py
```

工具会提示你为每个泄露地址输入替换邮件。
推荐使用 `ID+USERNAME@users.noreply.github.com` 格式
（在 `https://api.github.com/users/USERNAME` 可以找到你的数字 ID）。

**fix.py 的修复步骤：**

| 步骤 | 操作 | 安全性 |
|---|---|---|
| 1 | 生成/更新 `.mailmap` — 重写 `git log` 显示 | ✅ 安全 |
| 2 | 替换本地工作区文件中的邮件地址 | ✅ 安全 |
| 3 | 使用 `git filter-repo` 重写 git 历史 | ⚠️ 破坏性 — 需主动启用 |
| 4 | 打印 Profile 泄露的手动修复说明 | — 手动操作 |

### 提前指定替换地址

```bash
python fix.py --replace "old@example.com=12345+user@users.noreply.github.com"
```

### 重写 git 历史（破坏性操作）

```bash
# 先预览
python fix.py --dry-run --rewrite

# 确认后执行（无法撤销，请先备份）
python fix.py --rewrite

# 然后强制推送
git push --force-with-lease origin main
```

> **警告：** 历史重写后，所有协作者需重新克隆或 rebase。
> `git-filter-repo` 已包含在 `requirements.txt` 中，运行 `pip install -r requirements.txt` 即可安装。

---

## 安全邮件模式（不会被标记）

| 模式 | 示例 |
|---|---|
| `@users.noreply.github.com` | `12345+user@users.noreply.github.com` |
| `noreply@github.com` | `noreply@github.com` |
| `[bot]@` | `dependabot[bot]@users.noreply.github.com` |
| `@noreply.github.com` | `actions@noreply.github.com` |

以上模式之外的所有邮件地址均会被标记为潜在泄露。

---

## API 速率限制

使用 PAT 时，GitHub API 允许每小时 **5,000 次请求**。
扫描器会自动处理速率限制（通过读取 `X-RateLimit-Reset` 自动等待）。
对于大账号（100+ 个仓库、数千条提交），可能需要多次运行或适当降低 `--max-commits` 的值。

---

## 自检说明

本仓库的 GitHub Actions 工作流使用 `41898282+github-actions[bot]@users.noreply.github.com` 进行所有提交——不会触发自身的扫描器。

---

## 许可证

MIT
