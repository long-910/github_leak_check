# github-leak-check

**Language / 语言 / 言語:** [English](README.md) | [中文](README.zh.md) | 日本語

GitHub のコミット履歴・ファイル内容・プロフィールから `noreply` 以外のメールアドレスを検出し、結果をライブバッジとして GitHub プロフィールに表示します。

<!-- ステータスカード — GitHub Actions が毎日自動更新 -->
<!-- USERNAME をあなたの GitHub ユーザー名に置き換えてコメントアウトを解除 -->
<!-- ![スキャン状態](https://raw.githubusercontent.com/USERNAME/github_leak_check/main/results/card.svg) -->

---

## 背景・作成動機

### 「メールアドレスを非公開にしているのに、GitHub 関連の迷惑メールが増えてきた…」

GitHub の **"Keep my email addresses private"**（Settings → Emails）を有効にすると、**以降の**コミットのメールアドレスが `@users.noreply.github.com` に置き換わります。しかしこの設定は、**既存のコミット履歴を遡って修正することはありません。**

よくある漏洩パターン：

| パターン | 漏洩の原因 |
|---|---|
| **古いコミット** | 設定を有効にする前のコミット、またはローカルの `git config` に本物のアドレスが残ったまま |
| **強制プッシュ / rebase** | 履歴を書き換えても、古い author メタデータが commit オブジェクトに含まれたまま再公開される |
| **他サービスからの移行** | 別のホスティングから持ってきたリポジトリに元のメールアドレスが全コミットに残っている |
| **公開プロフィール** | プロフィールのメールフィールドは誰でも閲覧でき、スクレイピングの対象になりやすい |
| **ソースファイル** | `package.json`・`setup.py`・README・`.mailmap` などにメールアドレスを直接書いている |

### スパムボットがアドレスを見つける仕組み

ボットは GitHub のコミット API や検索インデックスを常時クロールしています。公開リポジトリのどこか1つのコミットに本物のアドレスがあれば、すぐにメーリングリストへ登録され、迷惑メールが届き始めます。

**このツール**は GitHub アカウント全体を自動・定期的に監査し、ボットに発見される前に漏洩箇所を把握できるようにします。

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

## 漏洩が見つかったときの対処法

### ステップ 0 — まず新たな漏洩を止める（最優先）

履歴を修正する前に、今後の漏洩を防ぎます。

1. **GitHub Settings → Emails**
   - **"Keep my email addresses private"** にチェック
   - **"Block command line pushes that expose my email"** にチェック

2. **ローカルの git config を更新**して、今後のコミットで noreply アドレスを使うようにします：
   ```bash
   # GitHub Settings → Emails で noreply アドレスを確認できます
   git config --global user.email "ID+USERNAME@users.noreply.github.com"
   ```

3. **設定を確認：**
   ```bash
   git config --global user.email
   # → ID+USERNAME@users.noreply.github.com と表示されればOK
   ```

---

### ステップ 1 — noreply アドレスを確認する

フォーマット：`ID+USERNAME@users.noreply.github.com`

数値 ID の確認方法：
```bash
curl https://api.github.com/users/YOUR_USERNAME | grep '"id"'
# または https://api.github.com/users/YOUR_USERNAME をブラウザで開く
```

例：ID が `12345678`、ユーザー名が `alice` なら noreply アドレスは：
`12345678+alice@users.noreply.github.com`

---

### ステップ 2 — プロフィール漏洩を修正する

スキャンで **profile** 漏洩が見つかった場合：

1. **https://github.com/settings/profile** を開く
2. **"Public email"** を探す
3. **"Don't show my email address"** に変更
4. 保存する

---

### ステップ 3 — ファイル内容の漏洩を修正する

README・package.json などのソースファイルにメールアドレスが含まれていた場合：

```bash
# 対話的に置換（推奨）
python fix.py

# 置換先を事前に指定する場合
python fix.py --replace "old@example.com=12345+alice@users.noreply.github.com"
```

修正後は通常通りコミット＆プッシュします：
```bash
git add .
git commit -m "fix: replace leaked email in source files"
git push
```

---

### ステップ 4 — コミット履歴の漏洩を修正する

最も複雑なステップです。状況に応じてどちらかの方法を選んでください。

#### 方法 A：`.mailmap` — 安全・履歴書き換え不要（まずこちらを推奨）

`.mailmap` を使うと、`git log`・`git shortlog`・GitHub の Contributors ページで表示されるメールアドレスを_別のものに見せる_ことができます。実際の commit オブジェクトは変更されないため、**完全に安全で元に戻せます。**

```bash
python fix.py   # .mailmap を自動生成
git add .mailmap
git commit -m "chore: add mailmap to mask leaked email"
git push
```

> **制限：** 実際の commit オブジェクトには古いアドレスが残り、GitHub API から取得可能です。完全に消したい場合は方法 B を使います。

#### 方法 B：`git filter-repo` — 完全な履歴書き換え（永続的な修正）

マッチする全コミットを永続的に書き換えます。**必ず事前にバックアップを取ってください。**

```bash
# 1. 変更内容をプレビュー（dry run）
python fix.py --dry-run --rewrite

# 2. 書き換えを実行
python fix.py --rewrite

# 3. 全ブランチを強制プッシュ
git push --force-with-lease origin main
git push --force-with-lease origin --all
```

> ⚠️ **強制プッシュ後の注意：**
> - すべての共同作業者は `git fetch && git reset --hard origin/main` または再クローンが必要
> - 他のユーザーが Fork したリポジトリには古い履歴が残ります — Fork 元に連絡してください
> - GitHub の検索インデックスのキャッシュは数日以内にクリアされます

#### どちらを選ぶべきか

| 状況 | 推奨 |
|---|---|
| 個人リポジトリ・共同作業者なし | 方法 B（完全書き換え） |
| チームリポジトリ・共同作業者あり | まず方法 A → コードフリーズ期間中に方法 B を調整実施 |
| アーカイブ済み / 読み取り専用 | 方法 A（安全・影響なし） |
| 多数の Fork にすでに拡散している | 方法 A（Fork は制御できないため） |

---

### ステップ 5 — 修正を確認する

`--full` オプションで再スキャンし、漏洩がなくなったことを確認します：

```bash
GH_PAT=ghp_... python scan.py YOUR_USERNAME --full --email your@real.address
```

クリーンな結果：
```
✅ Status: CLEAN
   Leaks found: 0
```

---

### fix.py クイックリファレンス

```bash
# 対話的（アドレスごとに入力を促す）
python fix.py

# 非対話的
python fix.py --replace "old@example.com=12345+alice@users.noreply.github.com"

# プレビューのみ（実際には変更しない）
python fix.py --dry-run

# 完全な履歴書き換え（確認あり）
python fix.py --rewrite
```

**fix.py の修正ステップ：**

| ステップ | 内容 | 安全性 |
|---|---|---|
| 1 | `.mailmap` を生成/更新 — `git log` の表示を書き換える | ✅ 安全 |
| 2 | ローカルのファイル内容を置換 | ✅ 安全 |
| 3 | `git filter-repo` で git 履歴を書き換える | ⚠️ 破壊的 — オプトイン |
| 4 | プロフィール漏洩の手動修正手順を表示 | — 手動 |

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
