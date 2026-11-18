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

PR本文は作成時点の結果と根拠の参照先を示す。[Git規約](../workflow/git.md#4-prレビュー統合)に従い、以後の通常の結果追記は次の専用コメントへ集約する。マージ後の本文更新もCI再起動の回避策にはならない。目的・受け入れ条件などの訂正で本文を改訂する場合は、UTF-8の本文ファイルを用意し、対象・内容と必要なCIを確認する。その他の PR 操作は `gh pr <操作> --help` で必要なオプションを確認する。

<a id="pr-results"></a>

### 検証・レビュー結果の専用コメントを更新する

投稿が依頼の範囲内であることを確認し、公開可能な結果・対象SHA・run URL・検証/レビュー記録への参照をUTF-8ファイルへまとめる。Python 3.10以上とGitHub.comのユーザー認証を設定したghを使い、repoとPR番号を明示する。

```sh
# 読み取り専用の確認。--checkを省略するとコメントを作成・更新する
python3 scripts/update_pr_results.py --repo "$gh_repo" --pr "$gh_pr" \
  --body-file "$gh_body_file" --check

python3 scripts/update_pr_results.py --repo "$gh_repo" --pr "$gh_pr" \
  --body-file "$gh_body_file"
```

この補助はPRの存在を確認し、認証ユーザー自身が作成した、固定マーカー `<!-- org-mobile-android-sample:verification-results:v1 -->` で始まるコメントだけを更新する。存在しなければ「検証・レビュー結果（更新）」コメントを作成し、本文が同じなら変更しない。ページ分割されたコメントも調べ、他者のコメントや通常の自分のコメントを上書きしない。マーカーと見出しは自動付与するため、入力ファイルへ含めない。専用コメントは同じ認証ユーザーで直列に更新する。

途中経過はChecksと保存した検証記録を参照し、専用コメントの更新はレビュー完了や統合後確認など必要な結果がそろった時点にまとめる。

標準出力は `created` / `updated` / `unchanged` とコメントURL、`--check` では `would-create` / `would-update`（または `unchanged`）。本文・生APIレスポンス・認証情報は返さない。入力不備は終了2、API失敗・不正応答・専用コメントの重複は終了1となり、自動再試行しない。書込み時に通信が失敗した場合は、変更が反映済みの可能性もあるため、まず `--check` で対象の状態を確認する。空入力・不正UTF-8・入力内の予約マーカーを拒否し、確認済み文字列を標準入力からghへ渡す。

PR本文・タイトル・CI設定は変更しない。PRへのこの種のコメントは [issue_comment](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#issue_comment) に対応し、現在の [android.yml](../../.github/workflows/android.yml) はこのイベントを購読していない。タイトル変更時の検証と必須 `verify`、統合後CIは維持する。別repoや将来のworkflow変更でコメントをCI起動条件にする場合は、この前提を見直す。コメントに成功と記載することは、対象SHA・必須チェックを直接確認する代わりにならない。

GitHub.comのowner/repo形式だけを扱う。権限の追加・認証方式変更・通知抑止は行わない。コメントの作成・更新は購読者へ通知される場合がある。[実装確認と未確認範囲](../records/evaluations/2026-11-16-pr-result-comments.md)を参照する。

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

端末上のE2Eと専用workflowは廃止済み。現在のCI確認は `Android checks` の対象SHA・run・必須 `verify` を確認する。

### 統合の各段階を記録して再開する

PR統合の定型操作には [integrate_pr.py](../../scripts/integrate_pr.py) を使える。Python 3.10以上、POSIX、Git、認証済みのGitHub CLIが必要。リポジトリのルートで、対象ブランチをpushし、独立レビューとローカル検証が終わったコミットの完全SHAを用意する。

| 段階 | 引数（共通の `--state` に追加） | 確認・操作 |
| --- | --- | --- |
| `prepare` | `--repo OWNER/REPO --head SHA` | 作業ツリー、ローカル・リモートの先端、最新mainとの関係、ブランチ保護を照合 |
| `create` | `--apply --title TITLE --body-file FILE` | 対象の既存PRを再利用するか、確認済み本文で作成 |
| `wait` | `--run RUN_ID` | 対象PRのCIを待ち、必須のverifyとrun・attemptを照合 |
| `artifacts` | 追加引数なし | 同じrunのレポートとAPKを取得し、カバレッジ、Lint、テストレポートの存在、APKハッシュ、検証対象コミットを照合 |
| `merge` | `--apply --title TITLE --body-file FILE` | レビュー済みSHAを指定してSquash mergeし、統合後の親とツリーを照合 |
| `main-ci` | `--run RUN_ID` | 統合後のmainで同じSHAのverify成功を確認 |
| `cleanup` | `--apply` | 統合とmain CI成功を再確認し、先端が変わっていないリモート作業ブランチを削除 |

```sh
python3 scripts/integrate_pr.py prepare --state .local/integration/work.json \
  --repo "$gh_repo" --head "$gh_sha"
python3 scripts/integrate_pr.py wait --state .local/integration/work.json --run "$gh_run"
```

表の順に同じ記録を指定する。再開時に `--repo` と `--head` を指定すると記録との一致を照合する。例の `wait` は `create` の後に実行する。書き込み段階ではその操作の許可を確かめてから `--apply` を付ける。PR本文とSquashコミット本文にはそれぞれ確認済みのファイルを指定する。ローカルブランチの切り替え・削除は、利用中の作業ツリーを確認したうえで既存のGit手順に従う。

完了した段階の再呼び出しは記録を返す。作成やマージの途中で通信が途切れた場合は、同じ記録で再開して既に反映された結果を確認する。反映を確認できない場合はGitHub上の状態を調べてから再開方法を判断する。先端・main・CI attemptが変わった場合は、新しい対象でレビュー・検証をそろえて新しい記録を使う。リモートブランチの削除には、削除直前に先端SHAが一致する場合だけ許可するGitのleaseを使う。 同じPRを操作する担当間では直列に進める。GitHubのマージAPIが更新時に照合するのはPR先端SHAであり、対象ブランチやmainのSHAは直前に照合する。PR作成APIには先端SHAの条件がないため、作成後にも照合する。

記録には成功した段階の秒数と照合結果が残る。モデルの入力・出力と失敗を含む全工程の時間は、比較試行の記録と合わせて評価する。 [比較試行の記録手順](trial-measurement.md)

### 成果物と保護設定の取得

成果物名は[ビルド・検証の手引き](android.md#ci)で確認し、`gh_artifact` に設定する。run ごとに新しい保存先を用意し、異なる run の APK とレポートを混ぜない。APK を使う場合は取得したファイルの SHA-256 も記録する。

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
