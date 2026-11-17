# E2E廃止・Robolectric移行の独立レビュー

作成者：主担当Codex。確認者：別agent review_e2e_removal。セルフレビューではない。
対象：main、HEAD `53a0a2eda8dc087eb20ecdd87ebc3d0be3c2ab51` からの未コミット差分と新規公開ファイル。ステージ済み差分なし。
既存の残タスク10件チェックリストは前タスクの成果として保持し、今回のE2E廃止注記・CA-008更新を確認する。
対象ファイルの編集・Git変更・GitHub操作・私的資料の取得は実施していない。本記録だけを作成した。

## 根拠

- RV1（確認者自身）：`python3 scripts/document_tools.py check`、80文書532ローカルリンク成功。`git diff --check` 成功。
- RV2（確認者自身）：`python3 -m unittest discover -s scripts/tests -q`、139件・失敗0・skip6、14.224秒。任意Kotlin構文木環境を使う6件は未実行。
- RV3（直接確認）：E2Eテスト・専用workflow・run_e2e.pyと専用Pythonテスト削除。GradleのManaged Device・runner・instrumentation依存削除。既存の製品ソース・必須verify・カバレッジ閾値は変更なし。
- RV4（直接確認）：MainActivityTest/OrgAdapterTestの選択結果注入、空文書、1万項目末尾、更新後の長文、取消・再作成後の位置、拡大横画面、48dp・見出し属性。実OS/System UI/権限・実プロバイダー、ATF全検査の非同等性を現行仕様・検証規則・guideへ明示。
- RV5（直接確認）：前提・許可・情報保護・独立レビュー・CIの記録条件を維持し、E2E実施要求だけを廃止。過去記録は保持し、削除ファイルへの参照は削除前HEAD固定URLへ更新。残タスクの既存チェックリストを保持。
- RV6（一次資料）：[Robolectric 4.16 RuntimeEnvironment](https://robolectric.org/javadoc/4.16/org/robolectric/RuntimeEnvironment.html) でsetFontScale/setQualifiers、[TextView API](https://developer.android.com/reference/android/widget/TextView#getMinHeight()) でピクセル単位の最小高さAPI、[Android公式Robolectric戦略](https://developer.android.com/training/testing/local-tests/robolectric) でUIテストへの利用とSystem UI等の限界を確認。
- RV7（主担当実行の結果を確認者が直接照合）：`python3 scripts/run_coverage.py --base-ref main` の最終summary・原ログ・JUnit XML・Lint XML・coverage comparison JSONを確認。clean後、Debug/Release各49件、計98件、失敗/error/skip各0。MainActivityTest各13件・OrgAdapterTest各2件を含む。LintはHint8件、エラー・警告0。行216/219（98.63%）、分岐83/89（93.26%）、比較対象の変更製品ソースなし。終了0。確認者自身のAndroid再実行とは扱わない。
- RV8（主担当実行の結果を確認者が直接照合）：最終OrgAdapterTestに対し48dp→1dp、見出し常時trueの一時変更を入れたログで2件のAssertionErrorを確認。初回は文字自体の高さによりタッチ領域縮小を見逃したため最低設定も検査するよう補強し、途中のView.minimumHeight/TextView.minHeight参照違いも修正した。失敗履歴は[移行記録](2026-11-18-robolectric-migration.md)へ保持。最終変異後の復元版がRV7で成功し、確認者自身の `git diff --exit-code -- app/src/main` でも製品原文との差分なしを確認。
- RV9（確認者自身）：最終APK SHA-256 `57d739a0dea08cd36d582adfb7da4c667c16116110eb9cfbd100604c3697d90a` が移行記録と一致。最終コード・文書差分を再確認し、80追跡文書532リンクと差分空白検査は成功。新規本レビュー記録を公開パスへ配置した後のリンク検査は主担当が実行する。

## 指摘と残るリスク

修正必須のコード・文書指摘は現時点でなし。改善提案：guideの「見出しノード属性」は現在の検査がView.isAccessibilityHeadingであるため「見出し属性」とする方が正確と通知し、主担当が修正。最終版で直接再確認して解消。
OS連携・描画・性能の未検証化は利用者が開発効率優先で明示選択し、移行記録で担当・再検討条件を定めている。Robolectric成功から実OS上の成功を推定しない。
R12の保存・入力利用条件を監査する根拠は提供されていないため未確認。今回の共有範囲は依頼対象の公開コード・文書に限定し、新規の外部サービスや私的資料共有はない。
GitHub CIは未実行。今回依頼はローカル変更までであり、公開・統合時は対象コミットの必須verifyを確認する。

## R01〜R30

| ID | 判定 | 根拠・理由 |
| --- | --- | --- |
| R01 | 確認済み | 利用者のE2E全廃・開発効率優先の指定とRV3〜RV5が対応 |
| R02 | 確認済み | RV4。空入力・取消・UTF-8エラー復帰・再選択・再読み込みを保持/補完 |
| R03 | 確認済み | RV3、Gradle API35 Robolectric 4.16とcompile/target37を区別。現行手順整合 |
| R04 | 確認済み | 未追跡2件を含む一覧と差分を確認。製品の無関係な変更なし |
| R05 | 確認済み | RV6の公式APIとRV7の最終コンパイル・実行成功。既存依存を再利用 |
| R06 | 確認済み | RV4〜RV6。将来の短縮量は未計測と明記 |
| R07 | 対象外 | 文字コード・型変換・製品の並行処理の変更なし |
| R08 | 確認済み | E2E操作処理削除とローカル検査の境界をRV3/RV4で直接追跡 |
| R09 | 確認済み | 製品ソース・責務・依存方向は不変 |
| R10 | 確認済み | 新規依存なし。既存Robolectric/プロバイダーの検査を拡張 |
| R11 | 確認済み | 既存の読み込み・失敗・競合テストを保持。レイアウト待機ヘルパーの変更を確認 |
| R12 | 未確認 | 共有を公開対象の必要範囲に限定したが、利用先の保存/入力利用条件の監査根拠は未提供。保守担当が必要時に確認 |
| R13 | 確認済み | RV3〜RV5。差分は公開コード・合成fixture・文書のみ。私的情報・生成物追加なし |
| R14 | 対象外 | 製品の入力検証・権限・アクセス経路・外部送信の変更なし |
| R15 | 対象外 | 新規の依存・外部素材・コード持込みなし |
| R16 | 確認済み | RV4。48dp、公開fixture、1万項目の具体的末尾等を仕様/既存E2Eから期待値化 |
| R17 | 確認済み | RV4/RV7。空文書・UTF-8失敗復帰・取消・再読み込み・拡大・末尾を両variantで検査 |
| R18 | 確認済み | RV8の2変異を最終検査で検出。初回見逃しと検査不備を記録し補強。更新文書の長さを維持し自然な位置補正だけの偽成功も防止 |
| R19 | 確認済み | RV1/RV2/RV7〜RV9の原結果を照合。初回失敗・変異・復元版を区別し、閾値緩和なし |
| R20 | 未確認 | ローカル検証RV7は成功。GitHub CIはpush/PR未依頼で未実行、公開・統合時に対象コミットのverifyを確認。実OS検査の廃止は利用者指定どおり |
| R21 | 確認済み | 日本語の入力・末尾・エラー復帰例を維持。テスト用URIのみ |
| R22 | 確認済み | 製品UI変更なし。拡大横画面・タッチ領域・見出し属性を検査。TalkBack等の限界を明示 |
| R23 | 確認済み | RV4/RV5。実OS上の成功と誤認しない現行説明に更新 |
| R24 | 確認済み | 多数の文書変更はE2E廃止に伴う同一方針の参照整合。製品コード変更なし |
| R25 | 確認済み | RV1/RV3/RV5。コード・Gradle・CI・guide・規則・様式・歴史リンクを照合 |
| R26 | 対象外 | 定量的な高速化・安定性改善の実証は主張していない |
| R27 | 対象外 | 製品データ・保存/移行・配布方法の変更なし |
| R28 | 確認済み | 利用者の選択と未検証になるOS境界、再検討条件を直接照合 |
| R29 | 確認済み | 必須指摘なし。残る未確認と確認者/契機を上記へ記録 |
| R30 | 確認済み | エミュレーター準備/操作保守を削除し、境界条件の高速検査を維持する利用者目的に対応 |

## 指示書保守19項目

| 番号 | 判定 | 根拠 |
| --- | --- | --- |
| 1 | 確認済み | 規則はworkflow、方法はguide、仕様はproject、履歴はrecordsへ維持 |
| 2 | 確認済み | E2E必須条件を削除し、ローカル/CIと未検証範囲を明確化 |
| 3 | 確認済み | 移行記録が目的・対象・手順・検証計画を記載 |
| 4 | 確認済み | developmentの変更種別による参照条件を更新 |
| 5 | 確認済み | RV1ローカルリンク成功、削除対象への参照を固定版URLへ変更 |
| 6 | 確認済み | 実在するcheck assembleDebugとrun_checkの例へ変更、E2E実行例を撤去 |
| 7 | 確認済み | 製品の閲覧専用動作・情報保護・既存作業保持を維持 |
| 8 | 確認済み | Git操作の許可範囲・必要時の承認条件を変更していない |
| 9 | 確認済み | AGENTS/.gitignoreの保護範囲は変更せず、私的資料取得なし |
| 10 | 確認済み | verificationに変更別テスト・CIと未検証範囲を記載 |
| 11 | 確認済み | review手順の別agent・初回30項目判定を維持 |
| 12 | 確認済み | 記録/PR様式のローカル検証・CI・未検証範囲を更新 |
| 13 | 確認済み | 既読資料の版/範囲再利用ルールは変更なし |
| 14 | 確認済み | 過去結果再利用条件は維持し、過去E2Eを現行保証にしないと明記 |
| 15 | 確認済み | 結果のID参照・記録集約を維持、生ログ再掲なし |
| 16 | 確認済み | proposal冒頭に旧E2E案が現行実行指示でないと明記 |
| 17 | 確認済み | E2E環境準備の必読経路を除去、JVM/Robolectricへ接続 |
| 18 | 確認済み | 移せる検査を追加し、実OS境界等の損失は利用者指定で未検証として明示 |
| 19 | 確認済み | 文書移動なし。削除参照・guide・様式・Gradle資産経路を整合 |

## 判定

ローカルのコード・文書変更と検証範囲は **採用可**。修正必須の指摘なし。E2Eを廃止し、移せる検査をJVM・Robolectricへ移した結果として確認した。

総合の公開・統合判定は **未確認のため保留**（R12の保存・入力利用条件の監査根拠、R20のGitHub CI）。今回のローカル変更完了を妨げるコード修正の要求ではなく、公開・統合時に保守担当が未確認事項を扱う。E2E未実行を保留理由にはしない。

## 最終対象版

本記録自体と、この後の本記録の公開パスへの転記は対象ハッシュから除く。製品コード・必須verify・coverage runnerはHEAD不変。

| ファイル | SHA-256／状態 |
| --- | --- |
| `.github/pull_request_template.md` | `42c7183607192f6ba94fbacbed7c0c2c8b9de4bac2edb06b987a29750fcd2074` |
| `.github/workflows/e2e.yml` | `deleted` |
| `README.md` | `dab8bccc805b50b0d2bc1ba129a4d0c476d3d9bca3474ade2ef1e5290d5d2de2` |
| `app/build.gradle.kts` | `460b2487e552cb8ec232f3e186cd7fc359030287766aae37265622fec2835fb0` |
| `app/src/androidTest/java/dev/orgmobile/reader/ReaderE2eTest.kt` | `deleted` |
| `app/src/test/java/dev/orgmobile/reader/MainActivityTest.kt` | `c26270dfc905fffa49aa1720dbe387269fe103c0923ec0950a7d58e8747d6307` |
| `app/src/test/java/dev/orgmobile/reader/OrgAdapterTest.kt` | `7ebc3cae555180000cea0204c482541679d8c27da9232a5993e9dc742700f0ec` |
| `docs/README.md` | `1a21b7790c06a7c0a00f23c821666391828101a935204a939250ed7292af439a` |
| `docs/guides/agent-tools.md` | `2aabb77bb4f66807557a4c80b8d344c5e125e8bfb94a266ccee36fc626173314` |
| `docs/guides/android.md` | `8523b52b9d7533e350fcc3a9ce4d0bfd64398b331af4810d171f012a3dd55d29` |
| `docs/guides/github-cli.md` | `4cb1ceea700c2d871bec9776eecaeb25ee7ebf28ff990d5f6b389395eb0fbd77` |
| `docs/maintenance/dependencies.md` | `f2be040764542f009897d8da221e035b70b2cec9a4a9053d2e8deba8a6aea85d` |
| `docs/project/app-spec.md` | `b2bc0756506c7cd46b378269ee551dd255b21a2e3187689fb93cc0588695dbdb` |
| `docs/project/architecture.md` | `6398bd11fecd64170835823e77ac54591b9cccd81517198356ce55233d42593e` |
| `docs/proposals/codex-adoption-recommendations.md` | `ef0085d179bf68a06914d45109c0170a916d37ad07ec766c6f407398e8c2e652` |
| `docs/proposals/codex-adoption-remaining-tasks.md` | `b4fc363fe988357f0cf57fda6e0b9fd4e98827a70449fa02e221e1587618ec05` |
| `docs/records/evaluations/2026-11-17-e2e-wait-efficiency.md` | `1d4b1e455575cdac892e4c4c33a22d3ead16982be0b34cacdaa624a85ac7506d` |
| `docs/records/verification/2026-11-18-robolectric-migration.md` | `37653a76e6a7cd66a7cb19012a32c1ed09d9a4a03feee2c2d90e11889d545206` |
| `docs/templates/codex-adoption-evaluation.md` | `b01e4c1792759d5f60211d48da9a0a1d354895616f68f4ffb7b6c1c77ab12ed7` |
| `docs/templates/handoff.md` | `443881146a9ad275d4956791ba4581b14a23c9e2d37b54dc8b46c656c0098f83` |
| `docs/templates/implementation-plan.md` | `c9eff2f047edc569464f5690935b4d2790fb27617dcd439d85fe080cc3e4781f` |
| `docs/workflow/design.md` | `81cfaf0a35bf64e8d2c265af1953c1fd07107bae8dbfde9a5062c82fb389397f` |
| `docs/workflow/development.md` | `6f588142a77c883620d112762fe8eeb37482b516020e17a219c4a962aa8ad7fe` |
| `docs/workflow/git.md` | `162be69aef0b009229b56b80e91ee5d790487f94a61b5d57aa16a78f41d5aa32` |
| `docs/workflow/release.md` | `66c6a2fa48c9858790b847471dca969229c515ffcb4d86bfa6d62c72345387c9` |
| `docs/workflow/review.md` | `c41769ce1aebc15c665086124a5b629fd56ed674251824f5dd97622fa7e22640` |
| `docs/workflow/verification.md` | `b423265d88447edda4d0e3268782d4e80e967c63b1bb019a5075a60d89617cad` |
| `scripts/run_e2e.py` | `deleted` |
| `scripts/tests/test_run_e2e.py` | `deleted` |
