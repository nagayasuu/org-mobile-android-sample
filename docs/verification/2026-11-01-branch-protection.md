# 必須 CI と main の保護の設定・検証記録

実施日：2026-11-01（日本時間）。対象：[nagayasuu/org-mobile-android-sample](https://github.com/nagayasuu/org-mobile-android-sample) の `main`。

## 目的と変更

PR と必須 CI を通して `main` に統合する方針を GitHub 側へ適用した。変更前は管理者への保護、強制 push・削除の禁止のみが有効であり、必須チェック・PR 要件・レビュー指摘の解決要件は設定されていなかった。既存のワークフローとアプリのコードは変更していない。

## 適用した設定

REST API の `PUT /repos/nagayasuu/org-mobile-android-sample/branches/main/protection` で更新し、別の GET リクエストで保存内容を確認した。設定フィールドは[GitHub の公式 API 仕様](https://docs.github.com/en/rest/branches/branch-protection#update-branch-protection)を参照した。

| 設定 | 保存後の値 |
| --- | --- |
| 対象ブランチ | `main` |
| 必須チェック | `verify` |
| 必須チェックの実行元 | GitHub Actions（`github-actions`、App ID `15368`） |
| 最新の main を要求 | `required_status_checks.strict: true` |
| PR を要求 | `required_pull_request_reviews` を有効化 |
| 必須承認数 | `required_approving_review_count: 0` |
| Code Owner／最後の push の承認 | どちらも不要 |
| 管理者にも適用 | `enforce_admins.enabled: true` |
| PR 要件を回避する例外 | なし |
| レビュー指摘の解決を要求 | `required_conversation_resolution.enabled: true` |
| 強制 push | `allow_force_pushes.enabled: false` |
| ブランチ削除 | `allow_deletions.enabled: false` |

追加の Ruleset は存在しなかった。既存のマージ方式の許可設定は変更せず、Squash merge が利用可能なことを確認した。統合時は Git 運用規約に従って Squash merge を選ぶ。

## 確認結果

- REST API で再取得した値を上表と照合し、必須チェックの名前・App ID、最新状態の要求、PR 要件、必須承認数、管理者適用、指摘の解決、強制 push・削除の禁止、回避例外なしが一致した。
- GraphQL API の `ref(qualifiedName: "refs/heads/main").branchProtectionRule` でも、`pattern: main`、`isAdminEnforced: true`、`requiresApprovingReviews: true`、`requiredApprovingReviewCount: 0`、`requiresStatusChecks: true`、`requiresStrictStatusChecks: true`、`requiredStatusCheckContexts: [verify]`、`requiresConversationResolution: true`、`allowsForcePushes: false`、`allowsDeletions: false` を確認した。
- `main` のコミット `c52ad4d81fb5fe51c5af8c1a92b1fad61a65231f` のチェック名が `verify`、実行元が GitHub Actions（App ID `15368`）、結論が `success` であることを確認した。[CI run](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/41308482255) は `Android checks`、ワークフローは `.github/workflows/android.yml`、実行契機は `push` だった。これは設定適用前の既存コミットの成功結果であり、今回の文書差分の CI 結果ではない。
- 文書差分は `git diff --check`、変更した4文書のローカルリンク・見出しアンカー54件の存在確認、ワークフロー名・ジョブ名・ビルドコマンドとの照合に成功した。

## 未確認と次の確認

設定時点でオープンな PR はなく、今回の作業では PR 作成・マージを行っていない。以下の実際の拒否・統合動作は未確認であり、設定 API の確認だけで検証済みとは扱わない。

- 管理者による `main` への直接 push、強制 push、削除の拒否。
- CI の実行待ち・失敗、最新の `main` 未反映、未解決のレビュー指摘がある PR の統合拒否。
- 条件を満たした PR の Squash merge と統合後の `main` の CI。

次の PR で[設定の維持と動作確認](../git-workflow.md#設定の維持と動作確認)に従い、条件未達時のマージ欄と条件達成後の結果を記録する。アプリ・ビルド・ワークフローの変更はないため、今回の設定・文書更新に対する APK 再生成と端末操作は省略する。
