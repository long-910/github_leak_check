# github-leak-check

**Language / 语言 / 言語:** [English](README.md) | [中文](README.zh.md) | 日本語

GitHub のコミット履歴・ファイル内容・プロフィールから `noreply` 以外のメールアドレスを検出し、結果をライブバッジとして GitHub プロフィールに表示します。

<!-- ステータスカード — GitHub Actions が毎日自動更新 -->
<!-- USERNAME をあなたの GitHub ユーザー名に置き換えてコメントアウトを解除 -->
<!-- ![スキャン状態](https://raw.githubusercontent.com/USERNAME/github_leak_check/main/results/card.svg) -->

---

## 機能

1. **コミットスキャン** — すべてのリポジトリの各コミットに含まれる `author.email` と `committer.email` を確認
2. **ファイルスキャン** — README・package.json・pyproject.toml などのファイル内からメールアドレスのパターンを検索
3. **プロフィールスキャン** — GitHub の公開プロフィールにメールアドレスが設定されていないか確認
4. `@users.noreply.github.com`（および他の bot/noreply アドレス）以外のすべてのアドレスを潜在的な漏洩として報告

出力ファイル：
- `results/summary.json` — 集計のみ、**実メールアドレスなし**（コミット対象）
- `results/card.svg` — プロフィール埋め込み用ステータスカード（コミット対象）
- `results/leaks.json` — 実アドレスを含む詳細データ（**.gitignore 済み、絶対にコミットしない**）

---

## セットアップ

### 1. このリポジトリをフォーク

GitHub Actions があなたの身元で実行されるよう、自分のアカウントにフォークしてください。

### 2. Personal Access Token を作成

**GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens** で、以下の権限を持つトークンを作成します：

| 権限 | アクセスレベル |
|---|---|
| **Contents** | Read-only（全リポジトリ） |
| **Metadata** | Read-only |
| **Email addresses** | Read-only（Account permissions 内） |

> クラシック PAT の場合：`repo` + `read:user` スコープで動作します。

### 3. トークンをリポジトリシークレットに登録

フォークしたリポジトリで：**Settings → Secrets and variables → Actions → New repository secret**

- 名前：`GH_PAT`
- 値：手順 2 で作成したトークン

### 4. Actions を有効化

フォークの **Actions** タブを開き、プロンプトが表示された場合はワークフローを有効化してください。
スキャンは毎日 03:00 UTC と `main` ブランチへの push 時に自動実行されます。
Actions タブから手動でトリガーすることも可能です。

### 5. プロフィール README にカードを埋め込む

`USERNAME/USERNAME` プロフィールリポジトリの README に以下を追記します：

```markdown
![メール漏洩スキャン](https://raw.githubusercontent.com/USERNAME/github_leak_check/main/results/card.svg)
```

`USERNAME` はあなたの GitHub ユーザー名に置き換えてください。

---

## ローカルで実行

まず依存パッケージをインストールします：

```bash
pip install -r requirements.txt
```

### macOS / Linux

```bash
# noreply以外の全メールアドレスをスキャン（ユーザー名とトークンを置き換えてください）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --verbose

# 特定のメールアドレスだけを検出
GH_PAT=ghp_... python scan.py YOUR_USERNAME --email your@example.com

# 複数のアドレスを同時に検出
GH_PAT=ghp_... python scan.py YOUR_USERNAME --email work@example.com --email personal@example.com

# 既存のサマリーからカードを生成
python generate_card.py

# ファイルスキャンをスキップ（高速化）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --no-files

# コミットスキャン深度を増やす（デフォルト：500件/リポジトリ）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --max-commits 2000
```

### Windows — PowerShell

```powershell
$env:GH_PAT = "ghp_..."

# noreply以外の全メールアドレスをスキャン
python scan.py YOUR_USERNAME --verbose

# 特定のメールアドレスだけを検出
python scan.py YOUR_USERNAME --email your@example.com

# 複数のアドレスを同時に検出
python scan.py YOUR_USERNAME --email work@example.com --email personal@example.com

# カードを生成
python generate_card.py

# ファイルスキャンをスキップ（高速化）
python scan.py YOUR_USERNAME --no-files

# コミットスキャン深度を増やす
python scan.py YOUR_USERNAME --max-commits 2000
```

### Windows — コマンドプロンプト（cmd.exe）

```cmd
set GH_PAT=ghp_...
python scan.py YOUR_USERNAME --verbose

python generate_card.py
```

---

## 漏洩の修正

`scan.py` 実行後、`fix.py` で漏洩したメールアドレスを置換します。

```bash
python fix.py
```

検出された各アドレスに対して置換先を対話的に入力します。
推奨フォーマットは `ID+USERNAME@users.noreply.github.com` です
（数値IDは `https://api.github.com/users/USERNAME` の `id` フィールドで確認できます）。

**fix.py の修正ステップ：**

| ステップ | 内容 | 安全性 |
|---|---|---|
| 1 | `.mailmap` を生成/更新 — `git log` の表示を書き換える | ✅ 安全 |
| 2 | ローカルのファイル内容を置換 | ✅ 安全 |
| 3 | `git filter-repo` で git 履歴を書き換える | ⚠️ 破壊的 — オプトイン |
| 4 | プロフィール漏洩の手動修正手順を表示 | — 手動 |

### 置換先をあらかじめ指定する

```bash
python fix.py --replace "old@example.com=12345+user@users.noreply.github.com"
```

### git 履歴の書き換え（破壊的操作）

```bash
# まずプレビュー
python fix.py --dry-run --rewrite

# 確認後に実行（バックアップ推奨、元に戻せません）
python fix.py --rewrite

# 実行後に強制プッシュ
git push --force-with-lease origin main
```

> **注意：** 履歴を書き換えると、すべての共同作業者が再クローンまたはリベースが必要になります。
> `git-filter-repo` は `requirements.txt` に含まれており、`pip install -r requirements.txt` でインストールされます。

---

## 安全と判定されるメールパターン（フラグなし）

| パターン | 例 |
|---|---|
| `@users.noreply.github.com` | `12345+user@users.noreply.github.com` |
| `noreply@github.com` | `noreply@github.com` |
| `[bot]@` | `dependabot[bot]@users.noreply.github.com` |
| `@noreply.github.com` | `actions@noreply.github.com` |

上記以外のアドレスはすべて潜在的な漏洩として報告されます。

---

## レート制限

PAT 使用時の GitHub API 制限は **5,000 リクエスト/時間** です。
スキャナーはレート制限を自動で処理します（`X-RateLimit-Reset` を読み取って自動待機）。
大規模アカウント（100+ リポジトリ、数千コミット）は複数回の実行か `--max-commits` の調整が必要な場合があります。

---

## 自己チェック

このリポジトリの GitHub Actions ワークフローはすべてのコミットに `41898282+github-actions[bot]@users.noreply.github.com` を使用しており、自身のスキャナーに検出されることはありません。

---

## ライセンス

MIT
