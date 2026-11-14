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

## PR を使った動作検証

`main` を危険な更新へさらさず拒否条件を確かめるため、一時ブランチ `ci/protection-validation-target` に同じ保護設定を複製した。チェック名・実行元・最新状態の要求・PR 要件・承認数・管理者適用・指摘解決・強制更新と削除の禁止を維持し、管理者権限を持つアカウントで実際の API 操作を試した。検証用の `verify` は同じ GitHub Actions App による短いジョブとし、意図的な失敗と成功を切り替えた。アプリのビルド成功は下記の本番 PR の CI で別に確認した。

| 条件・操作 | 実際の結果 |
| --- | --- |
| CI 実行中にマージ | HTTP 405、`Required status check "verify" is in progress.` |
| CI 失敗後にマージ | HTTP 405、`Required status check "verify" is failing.` |
| CI 成功後もレビュー指摘が未解決 | HTTP 405、`All comments must be resolved.` |
| 最新の統合先を取り込まずにマージ | `mergeable_state: behind`、HTTP 405、`Required status check "verify" is expected.` |
| PR のないコミットを直接更新 | CI 成功後も HTTP 422、`Changes must be made through a pull request.` |
| 古いコミットへ強制更新 | HTTP 422、`Changes must be made through a pull request. Cannot force-push to this branch` |
| 保護ブランチを削除 | HTTP 422、`Cannot delete this branch` |
| CI 成功・最新の基点反映・指摘解決後に Squash merge | HTTP 200、`merged: true` |

拒否ケースは [PR #6](https://github.com/nagayasuu/org-mobile-android-sample/pull/6) で検証した。[失敗 CI](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/41309192431) の対象は `a082457a61973c29ffd7ec07e231a60c472cf64a`、[成功 CI](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/41309298063) の対象は `094e9068f9c5d9741aab737f869e3f955a105536`。未解決のスレッドは拒否確認後に解決した。

[PR #7](https://github.com/nagayasuu/org-mobile-android-sample/pull/7) を成功 CI と Squash merge で統合先へ反映してから、PR #6 が古い基点として拒否されることを確認した。共有済みの検証ブランチは merge で最新の基点を取り込み、履歴を書き換えていない。

PR を持たない直接更新の検証は `b91bdfc12d96d4e78a5c6eec6a6d1f6d02ed564c` の [push CI](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/41309483284) の成功と、当該コミットに PR がないことを確認してから行った。成功 CI と PR 要件を分離して検証している。

正常統合は [PR #8](https://github.com/nagayasuu/org-mobile-android-sample/pull/8) で確認した。対象コミット `e61798be82c2d2021167b184436ef3ba9bb2094d` をマージ API に指定し、[成功 CI](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/41309490277) を確認して Squash merge した。統合コミットは `9d6332e773b318d17a60ca0935e7de40b0fe65ac`。

### 検証で確認した GitHub の挙動と保証範囲

条件を満たした既存 PR #6 の先端 `99cca6ac92df09543f544152a2f0de999d6c84cd` への REST refs API による fast-forward 更新は許可され、PR #6 は統合済みになった。PR 要件は「マージ API 以外からのすべての参照更新を拒否する」という制約ではない。PR のない更新は上記のとおり、CI が成功していても拒否された。通常の統合操作には規約どおり Squash merge を使う。

拒否操作と意図的な CI 失敗は一時ブランチだけで実行し、`main` への強制更新・削除は試していない。一時 PR #6・#7・#8 はすべて統合済みとなり、一時ブランチと一時ターゲットの保護設定は削除した。削除後も `main` の保護設定が維持され、その時点で先端が `c52ad4d81fb5fe51c5af8c1a92b1fad61a65231f` のままであることを確認した。検証用ワークフロー・合成ファイルは `main` 向け PR へ含めていない。

## main 向け PR の検証

本番の文書変更は [PR #5](https://github.com/nagayasuu/org-mobile-android-sample/pull/5) で統合する。初回の対象コミット `61a52dad6dda42461388cc0e0dd84d967ca7ec39` の [CI run](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/41309121761) は成功し、ビルド・Lint・Debug / Release の JVM テスト各26件（失敗・スキップ0件）、APK とレポートの保存を確認した。Lint はエラー・警告0件、既存の Hint が7件だった。

この記録を含めた最終コミットの CI を確認してから、PR #5 を保護条件を維持したまま Squash merge し、統合コミットの `main` 向け push CI も確認する。最終結果は PR の Checks と統合コミットの Actions、および完了報告で追跡する。アプリ・ビルド・ワークフローの変更はないため、今回の文書更新に対する APK のローカル再生成と端末操作は省略する。
