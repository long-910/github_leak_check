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

输出文件说明：
- `results/summary.json` — 汇总统计，**不含真实邮件地址**（会提交到仓库）
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

### 3. 将 Token 添加为仓库密钥

在你的 Fork 中：**Settings → Secrets and variables → Actions → New repository secret**

- 名称：`GH_PAT`
- 值：第 2 步创建的 Token

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
# 扫描（替换为你的用户名和 Token）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --verbose

# 从已有摘要生成卡片
python generate_card.py

# 跳过文件内容扫描（更快）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --no-files

# 增加每仓库的提交扫描深度（默认：500）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --max-commits 2000
```

### Windows — PowerShell

```powershell
# 扫描
$env:GH_PAT = "ghp_..."
python scan.py YOUR_USERNAME --verbose

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
python scan.py YOUR_USERNAME --verbose

python generate_card.py
```

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
