# GitHub CLI を使う手順への統一

## 対象と受け入れ条件

比較元は `7f0095b`。今回の対象は AGENTS.md、開発手順、Git 運用規約、ビルド・検証の手引きと本記録。依頼前からの未コミット変更は保持した。

- GitHub 上の操作に `gh` を使う方針を4文書で統一する。
- 準備・対象指定・出力の絞り込み・標準コマンドを[Git 運用規約](../git-workflow.md#github-cli)へ集約する。
- 既存 PR・CI・成果物を使い、読み取り操作の動作を確認する。
- 投稿・CI の起動・設定変更・マージの実行条件と、既存の検証・レビュー基準を維持する。

## 環境と実行範囲

主担当の Codex agent が `gh` 2.102.0、Python 3、Git、Bash を使って確認した。GitHub への通信は、実行環境のポリシーに従い、ネットワーク制限外での実行許可を得て行った。認証は有効であり、再ログインは行っていない。認証情報やアカウント設定の内容は記録しない。

ローカルの編集・ビルド・テストのために `gh` を要求する変更はしていない。この読み取りの動作確認では、アプリのビルド・CI・E2E を起動していない。以下の CI 結果は過去の実行を使った取得手順の確認であり、今回の変更の CI 成功を示さない。公開・統合時に実行する必須 CI の結果は、対応する PR に記録する。

## 検証結果

| ID | 確認と結果 |
| --- | --- |
| V1 | `gh --version`、`gh auth status --active --hostname github.com`、`gh repo view --json nameWithOwner,url,viewerPermission` が成功。リポジトリのルートから接続先とアクセス権を確認 |
| V2 | `gh pr list`、`gh pr view`、`gh pr checks --required --json name,bucket,link`、`gh run list --commit`、`gh run view --json` が成功。PR・コミット・run の対応と必須チェックを確認 |
| V3 | `gh pr checks --required --watch --interval 30` が完了済み PR に対して終了0。最終結果は `verify` / `pass` |
| V4 | 同じ run の `android-reports` と `org-reader-debug` を `gh run download` で一時ディレクトリへ取得、終了0。レポート104ファイルと APK を確認 |
| V5 | 過去の失敗 run に `gh run view --log-failed` を実行、終了0。ログが空でなく、失敗の詳細を含むことを確認。生ログは公開記録に転載していない |
| V6 | `gh api --method GET` による `main` の保護設定の取得が成功。第4節の条件と照合。設定の更新は行っていない |
| V7 | 対象文書の内容・ローカルリンク／アンカー、シェル実行例の構文、`git diff --check` を確認。標準コマンドのオプションはインストール済み CLI のヘルプとも照合 |

V1〜V6 の各コマンドは終了0。V7 の未追跡ファイルに対する `git diff --no-index --check` は、差分ありの終了1と空白エラーの診断を区別して確認した。

### PR・CI・成果物の対応

- PR：[PR #29](https://github.com/nagayasuu/org-mobile-android-sample/pull/29)。確認時点では統合済み。
- PR の `headRefOid` と run の `headSha`：`f508e35906cc47b7fb6db6252ea7b8a53dd14670`。
- CI：[run 42339958378](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/42339958378)、attempt 1、`pull_request`、`completed` / `success`。
- 必須チェック：`verify` / `pass`。チェックのリンクも同じ run を指していた。
- APK：`org-reader-debug` 内の `app-debug.apk`、3,003,468 bytes、SHA-256 `7e664d705997d1e81d8e3ea81ddec19ac81584b9086a5cec89b933820dda014e`。
- 失敗ログの取得対象：[run 42122147230](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/42122147230)、attempt 1、`completed` / `failure`。コミットは `1420ed8773d093a7264963c3ebebc4e49b632e54`。この失敗を修正・再実行する作業は行っていない。

保護設定は、管理者への適用と最新状態の要求が有効、必須チェックが `verify` / App ID `15368`、必須承認0、会話の解決が必要、強制 push・削除が禁止であることを読み取った。

## 読み取りの動作確認で未実行・未確認の範囲

この動作確認では、PR 作成、コメント投稿、CI 起動、設定更新、承認、マージは実行していない。標準の PR 作成例は CLI ヘルプとシェル構文の確認までとした。公開・統合の操作とその結果は、対応する PR の記録で区別する。

待機コマンドは完了済み PR で確認した。進行中の CI の待機、終了コード8、失敗・キャンセル・スキップ・チェック欠落などの全分岐を今回のリポジトリで再現して検証した結果ではない。統合済み PR の `mergeable` と `mergeStateStatus` は `UNKNOWN` であり、未統合 PR のマージ可否の検証にも使っていない。

トークン使用量の削減率は計測していない。必要なフィールドや失敗箇所に出力を絞る手順を整備した段階である。
