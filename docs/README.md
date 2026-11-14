# 開発文書の案内

[AGENTS.md](../AGENTS.md)は agent の入口、[README](../README.md)は利用者と開発者の入口。規則・仕様の本文は下表の正本に集約する。

| 区分・文書 | 役割と読む条件 |
| --- | --- |
| [アプリ仕様](project/app-spec.md) | 現在の対応機能・維持する動作・制約・保証の限界。動作を調べるとき・変えるとき |
| [アーキテクチャ](project/architecture.md) | 現在の責務・依存方向・状態とデータの流れ。構造を調べるとき・変えるとき |
| [開発手順](workflow/development.md) | 着手・受け入れ条件・実装・完了報告の進め方。ファイルを変更するとき |
| [設計変更の判断基準](workflow/design.md) | 要求・品質・境界・保存・同期の設計条件。関係する判断を行うとき |
| [検証の基準](workflow/verification.md) | 検証の選択・実行条件・合否基準。変更の検証を選ぶとき |
| [レビュー手順](workflow/review.md) | 確認者・R01〜R30・判定・再確認・記録。変更をレビューするとき |
| [Git 運用規約](workflow/git.md) | 操作の範囲・ブランチ・コミット・統合・履歴・保護条件。Git を操作するとき |
| [一般配布の開始条件](workflow/release.md) | 一般配布を始めるための準備と保証。配布に着手するとき |
| [Android の手引き](guides/android.md) | 環境・実行コマンド・レポート。ビルド・テスト・E2E・計測を実行するとき |
| [GitHub CLI の手引き](guides/github-cli.md) | gh の認証・操作・結果取得。GitHub を操作するとき |
| [agent ツールの手引き](guides/agent-tools.md) | 検索・文書取得・ログ・既読記録・使用量計測。必要な補助を使うとき |
| [指示書の保守](maintenance/agent-instructions.md) | AGENTS.md・参照文書・skills の分担と保守チェックリスト。指示を変更するとき |
| [依存と開発環境の更新](maintenance/dependencies.md) | 更新判断と未導入の自動確認方針。依存・環境を更新するとき |
| [開発フローの評価](maintenance/evaluation.md) | 改善案の比較・採否・見直し方法。運用の効果を評価するとき |
| [実装計画](templates/implementation-plan.md)・[レビュー記録](templates/review-record.md)・[引き継ぎ](templates/handoff.md) | 記入様式。規則や基準の本文は複製しない |
| [記録](records/README.md) | 過去の決定・検証・評価の証拠。現在の規則とは区別する |
| [検討資料](proposals/README.md) | 未採用案・下書き。採用された作業指示として扱わない |

設定・動作・操作方法を変更したら、対応する正本と必要な参照元を同じ変更で更新する。公開ファイルだけで理解・実行できる状態を保ち、ローカル専用資料を前提にしない。検証やレビューの要件を手引きへ複製せず、手引きには正本への参照と実行方法を記載する。
