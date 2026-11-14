# agent 指示書と参照文書の再構成

## 目的と受け入れ条件

既存パスの維持を前提にせず、AGENTS.md と参照文書を役割ごとに整理する。利用者が選んだ `app-spec.md` を現在のアプリ仕様の正本とする。

- AGENTS.md は共通制約と作業別の入口を示し、規則の本文を複製しない。
- 現在の仕様・構造、作業規則、実行手引き、保守、様式、過去の記録、未採用案を分ける。
- 必須検証、R01〜R30、確認者の選択、操作の許可範囲、情報保護の要件を維持する。
- 文書・skills・PR テンプレート・文書取得ツールとテストの参照先をそろえる。
- 既存の未追跡ドラフトは内容を保って検討資料へ移し、無関係な作業を含めない。

アプリ本体、依存、CI 定義、GitHub の保護設定は変更しない。コミット・push・PR 投稿は今回の依頼に含めない。

## 配置と判断

正本と読む条件は [開発文書の案内](../../README.md)へ集約した。

| 以前の内容 | 新しい配置 |
| --- | --- |
| 開発手順の現在の動作・制約 | [アプリ仕様](../../project/app-spec.md) |
| 現在の責務・依存関係 | [アーキテクチャ](../../project/architecture.md)。コードを直接確認して追加 |
| 着手・受け入れ条件・実装・完了報告 | [開発手順](../../workflow/development.md) |
| 要求・設計・保存や同期の着手条件 | [設計変更の判断基準](../../workflow/design.md) |
| 必須検証・テスト選択・CI・E2E の条件 | [検証の基準](../../workflow/verification.md) |
| 確認者・R01〜R30・再確認と判定 | [レビュー手順](../../workflow/review.md) |
| Git 規則と gh の実行方法 | [Git 規約](../../workflow/git.md)と[GitHub CLI の手引き](../../guides/github-cli.md) |
| Android の実行方法 | [Android の手引き](../../guides/android.md) |
| 文書取得・探索・ログ・既読・使用量集計 | [agent ツールの手引き](../../guides/agent-tools.md) |
| 一般配布の条件、依存更新、開発フロー評価 | 専用の workflow・maintenance 文書 |
| 指示書のチェックリスト | [指示書の保守](../../maintenance/agent-instructions.md) |
| notes と過去の検証・比較 | proposals、records/verification、records/evaluations |

現在の構造の説明と構造を変更する際の判断基準を混ぜないため、`workflow/design.md` を設けた。一般配布・更新・評価は関係する作業でだけ参照する。ADR は作成条件を保持し、個別の判断記録を今回新設したとは扱わない。

過去の記録は対象版と判断を保ち、移動後の参照と再実行用の文書パスを更新した。未追跡だったドラフトも公開の検討資料として保持し、現在の作業指示とは区別した。変更前の対象は基準コミット `e43d080` と作業開始時の未追跡ドラフトである。

## 検証

実行者：作成 agent。環境：作業環境の Python 3 と Git。対象：`docs/reorganize-agent-guidance` の未コミット差分と新規公開文書。後続のレビュー記録は別途示す。

| ID | コマンド・確認 | 結果 |
| --- | --- | --- |
| V1 | 変更前の `python3 -m unittest discover -s scripts/tests -p test_agent_tools.py -q` | 36件成功 |
| V2 | 変更後の同コマンド | 36件成功。複数の正本文書からの取得、全R項目・判定方法、重複排除、失敗時の原子性、既読記録を維持 |
| V3 | `python3 -m unittest discover -s scripts/tests -q` | 98件実行、失敗なし、6件 skip。任意の Kotlin 構文木環境を用いる6件は未実行 |
| V4 | Git の追跡済み・未追跡・非除外の Markdown のうち現存するパスを明示し、`python3 scripts/document_tools.py check <paths...>` | 初回60文書・362リンク成功。本記録追加後も61文書・378リンク成功。レビュー記録追加後の検査はレビュー記録を参照 |
| V5 | `python3 scripts/document_tools.py context change --include docs/guides/agent-tools.md document-tools check-output` と `context review`、`read docs/project/app-spec.md 現在の動作` | 終了コード0。新構成の正本と実際の例で原文を取得できる |
| V6 | `git diff --check`、旧パス参照・分割前の節番号・相対リンク・新規ファイルの内容確認 | 差分の空白エラーなし。リンク検証に加え、コマンドと取得ツールの参照も更新 |
| V7 | 評価 JSON 10件を基準コミットの `git show HEAD:<旧パス>` と SHA-256 で照合し、JSON を解析 | 全10件が基準版とバイト一致し、解析成功。固定プロンプト内の旧パスは当時の実験入力として保持 |
| V8 | 同リポジトリの `blob/main` を指す絶対 URL を現在の配置・アンカーと照合 | 3件成功。外部 URL を無条件に除外するローカルリンク検査を補完 |

Android のコード・テスト・設定を変更していないため APK 再生成・Android E2E は対象外。Python 補助ツールの差分には Python 全体テストを実施した。GitHub CI は push・PR 作成を行わず未実行であり、ローカルの成功を CI の成功として扱わない。

## 情報の取り扱い

[既存の利用者確認](../evaluations/2026-11-07-instruction-reading.md)と[継承の確認記録](../evaluations/2026-11-14-adoption-remaining-tasks.md)を参照する。今回も同じ既存環境で、公開文書・必要な差分・合成テストに範囲を限定する。別サービスや私的な文書への共有許可へ広げず、保存条件の監査済みとは主張しない。

## レビューと残る確認

文書の役割・参照経路と Python の取得対象を変更するため、表記修正のセルフレビュー例外には該当しない。[レビュー手順](../../workflow/review.md#agent-review)に従い別 agent による全R項目の確認を依頼する。

確認者は作成 agent と別の `review_guidance` agent。対象版、R01〜R30の判定と根拠、初回指摘と再確認、総合判定は [独立レビュー記録](2026-11-14-agent-guidance-review.md)を参照する。

初回レビューで、Markdown リンクではない JSON 根拠パスの不整合を検出した。旧ディレクトリに残っていた評価 JSON 10件を内容を変えず `records/evaluations/` へ移し、Markdown のリンクと表内の根拠パスを修正した（V7）。改善提案のあった Git 規約から CI の基準への参照も、検証の正本へ直接向けた。

使用量・所要時間の削減効果は未計測。次の同種作業で保守担当が [評価手順](../../maintenance/evaluation.md)に従って確認する。パス移動を行っただけで改善率を保証しない。
