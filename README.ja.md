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
5. **差分スキャン** — 2回目以降は前回スキャン時刻以降のコミットのみを対象にする
6. **フォークをデフォルト除外** — `--include-forks` を指定しない限り、フォークしたリポジトリはスキップされる

出力ファイル：
- `results/summary.json` — 集計のみ、**実メールアドレスなし**（コミット対象）；`since` フィールドで今回のスキャン範囲を記録
- `results/card.svg` — プロフィール埋め込み用ステータスカード（コミット対象）
- `results/leaks.json` — 実アドレスを含む詳細データ（**.gitignore 済み、絶対にコミットしない**）

---

## GitHub Action として使う

任意のリポジトリのワークフローに2行で組み込めます：

```yaml
- uses: actions/checkout@v4

- name: メール漏洩スキャン
  uses: long-910/github_leak_check@v1
  with:
    github-token: ${{ secrets.GH_PAT }}
```

### 全入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `github-token` | 必須 | — | `repo` + `read:user` スコープの PAT |
| `username` | 任意 | リポジトリオーナー | スキャン対象の GitHub ユーザー名 |
| `target-emails` | 任意 | _(すべて)_ | 監視するアドレス（カンマ区切り） |
| `max-commits` | 任意 | `500` | リポジトリごとの最大スキャンコミット数 |
| `include-forks` | 任意 | `false` | フォークリポジトリも含める |
| `no-files` | 任意 | `false` | ファイル内容スキャンをスキップ |
| `full-scan` | 任意 | `false` | 前回のスキャン時刻を無視して全スキャン |
| `max-rate-wait` | 任意 | `60` | N秒超の待機が必要なら中止 |
| `output-dir` | 任意 | `results` | 出力ディレクトリ |

### 出力

| 出力 | 説明 |
|---|---|
| `status` | `CLEAN` \| `LEAKS_FOUND` \| `RATE_LIMITED` \| `ERROR` |
| `leak-count` | 検出した漏洩の件数 |
| `exit-code` | `0` クリーン · `1` 漏洩あり · `2` レート制限 |

---

## セットアップ（セルフホスト / Fork）

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

### 3. シークレットをリポジトリに登録

フォークしたリポジトリで：**Settings → Secrets and variables → Actions → New repository secret**

| シークレット名 | 必須 | 値 |
|---|---|---|
| `GH_PAT` | 必須 | 手順 2 で作成したトークン |
| `TARGET_EMAILS` | 任意 | 監視するメールアドレス（カンマ区切り）例：`you@work.com,old@isp.net` |

`TARGET_EMAILS` を設定しない場合、スキャナーはリポジトリ内の**すべての**非 noreply アドレスを報告します。
設定した場合は、指定したアドレスだけを検出対象にします。

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
# 前回スキャン以降のコミットだけを対象にする（デフォルト — summary.json から自動読み込み）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --verbose

# 前回の結果を無視して全コミットをスキャン
GH_PAT=ghp_... python scan.py YOUR_USERNAME --full

# 指定した日時以降のコミットをスキャン
GH_PAT=ghp_... python scan.py YOUR_USERNAME --since 2026-01-01T00:00:00Z

# フォークしたリポジトリも含めてスキャン（デフォルト除外）
GH_PAT=ghp_... python scan.py YOUR_USERNAME --include-forks

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

# 前回スキャン以降のコミットだけを対象にする（デフォルト）
python scan.py YOUR_USERNAME --verbose

# 前回の結果を無視して全コミットをスキャン
python scan.py YOUR_USERNAME --full

# 指定した日時以降のコミットをスキャン
python scan.py YOUR_USERNAME --since 2026-01-01T00:00:00Z

# フォークしたリポジトリも含めてスキャン
python scan.py YOUR_USERNAME --include-forks

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

REM 前回スキャン以降のコミットだけを対象にする（デフォルト）
python scan.py YOUR_USERNAME --verbose

REM 前回の結果を無視して全コミットをスキャン
python scan.py YOUR_USERNAME --full

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
