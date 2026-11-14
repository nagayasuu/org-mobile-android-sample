# GitHub CLI の手引き

GitHub 上の操作を `gh` で実行する方法。操作してよい範囲と統合条件は [Git 運用規約](../workflow/git.md)に従う。

<a id="github-cli"></a>

## 8. GitHub CLI による操作

GitHub 上の PR・Issue 操作、CI の確認・起動、成果物の取得、リポジトリ設定の確認・更新には `gh` を使う。REST / GraphQL API が必要な場合も `gh api` を使う。ローカルの編集・ビルド・テストに `gh` の準備は要求せず、コミットや push には引き続き `git` を使う。

投稿・CI の起動・設定変更・承認・マージは、[Git 規約の操作範囲](../workflow/git.md#6-codex-が作業するときの手順)に従う。読み取りの動作確認には、既存の PR・CI と成果物を使う。

### 準備と接続の確認

GitHub 上の操作が必要になった時点で `gh` の導入、認証、対象リポジトリへのアクセスを確認する。CLI の入手先とオプションは[公式マニュアル](https://cli.github.com/manual/)を参照する。

```sh
gh --version
gh auth status --active --hostname github.com
gh repo view --json nameWithOwner,url,viewerPermission
```

認証が必要な場合は、利用者が `gh auth login --hostname github.com --web` でログインする。トークンの実体を表示・記録しない。認証の手順は[公式の認証ガイド](https://docs.github.com/en/github-cli/github-cli/authenticating-with-github-cli)に従う。

接続に失敗した場合は、ネットワーク制限、認証、操作権限を切り分ける。通信が制限された環境での失敗だけを認証切れと判断せず、環境のポリシーに従って通信の許可を得たうえで再確認する。解決できない GitHub 上の操作は未確認として理由と次の確認方法を記録し、進められるローカル作業を続ける。

### 対象と出力を絞る

以下はリポジトリのルートで実行する。`gh_repo` は取得・操作先を固定するための値であり、各コマンドにも明示する。

```sh
gh_repo='nagayasuu/org-mobile-android-sample'
```

各例の `gh_pr`、`gh_run`、`gh_sha` は確認する PR 番号、run ID、コミット SHA を設定する。取得前に対象を確かめ、最新の別 run で代用しない。情報の取得には `--json` と必要なフィールドを指定し、必要なら `--jq` でさらに絞る。生ログは必要な箇所だけを読み、成否・対象・詳細の保存先を記録する。

### PR の確認・作成

```sh
gh pr list --repo "$gh_repo" --state all --limit 5 \
  --json number,headRefName,headRefOid,state,url
gh pr view "$gh_pr" --repo "$gh_repo" \
  --json number,headRefOid,baseRefName,state,mergeable,mergeStateStatus,reviewDecision,url
```

PR 作成を依頼された場合は、先に `git` で対象ブランチを push する。公開可能な本文を [PR テンプレート](../../.github/pull_request_template.md)に沿って一時ファイルへ記入し、そのパスを `gh_body_file`、タイトルを `gh_title`、作業ブランチ名を `gh_branch` に設定する。複数行の本文は `--body-file` で渡す。

```sh
gh pr create --repo "$gh_repo" --base main --head "$gh_branch" \
  --title "$gh_title" --body-file "$gh_body_file"
```

コメントや PR 本文の更新にも本文ファイルを使い、投稿前に内容と対象を確認する。その他の PR 操作は `gh pr <操作> --help` で必要なオプションを確認する。

### CI の状態・失敗箇所の確認

```sh
gh pr checks "$gh_pr" --repo "$gh_repo" --required --json name,bucket,link
gh run list --repo "$gh_repo" --workflow android.yml --commit "$gh_sha" --limit 5 \
  --json databaseId,headSha,event,status,conclusion,url
gh run view "$gh_run" --repo "$gh_repo" \
  --json databaseId,attempt,headSha,event,status,conclusion,url
```

PR の `headRefOid`、チェックのリンク、run の情報から対象の対応を確認する。PR 用のマージコミットで検証される場合は、その関係も記録する。対象の run が見つからなければ未確認とし、別コミットの成功で置き換えない。

CI は `status` が `completed` で `conclusion` が `success`、かつ必須チェック `verify` が成功していることを確認する。実行待ち、キャンセル、スキップ、チェックの欠落を成功とみなさない。`gh pr checks` の終了コード8は実行待ちを表す。

完了を待つ場合は次のコマンドを使う。繰り返し出る状態一覧はそのまま報告へ転記せず、最終結果と参照先を残す。

```sh
gh pr checks "$gh_pr" --repo "$gh_repo" --required --watch --interval 30
```

失敗時は、対象 run またはジョブの失敗したステップに絞ってログを取得する。

```sh
gh run view "$gh_run" --repo "$gh_repo" --log-failed
```

手動 E2E の起動を依頼された場合は、`gh_branch` に実行するブランチ名を設定して起動する。その後の run は `e2e.yml` と対象コミットで絞って確認する。起動の成功とテストの成功を区別する。

```sh
gh workflow run e2e.yml --repo "$gh_repo" --ref "$gh_branch"
```

### 成果物と保護設定の取得

成果物名は[ビルド・検証の手引き](android.md#ci)と[E2E の結果](android.md#結果と成果物)で確認し、`gh_artifact` に設定する。run ごとに新しい保存先を用意し、異なる run の APK とレポートを混ぜない。APK を使う場合は取得したファイルの SHA-256 も記録する。

```sh
gh_download_dir=$(mktemp -d)
gh run download "$gh_run" --repo "$gh_repo" \
  --name "$gh_artifact" --dir "$gh_download_dir"
```

保護設定は `gh api` で読み取り、必要な項目に絞る。取得した値は[Git 規約の保護条件](../workflow/git.md#必須-ci-と-main-の保護)と照合する。設定の変更は、変更内容と影響を確認してから、依頼の範囲内で `gh api` の更新操作を行う。

```sh
gh api --method GET "repos/$gh_repo/branches/main/protection" \
  --jq '{enforce_admins: .enforce_admins.enabled, strict: .required_status_checks.strict, checks: .required_status_checks.checks, approvals: .required_pull_request_reviews.required_approving_review_count, resolve_conversations: .required_conversation_resolution.enabled, allow_force_pushes: .allow_force_pushes.enabled, allow_deletions: .allow_deletions.enabled}'
```

コマンドの仕様は [PR チェック](https://cli.github.com/manual/gh_pr_checks)、[run の取得](https://cli.github.com/manual/gh_run_view)、[成果物の取得](https://cli.github.com/manual/gh_run_download)を参照する。
