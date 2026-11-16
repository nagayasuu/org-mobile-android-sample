# 最終E2E前のビルド構成・比較条件の確認

## 実装前の計画

基準HEADは `28b6d5a`。待機監視・PR結果コメント・改善提案の既存未コミット変更を保持する。対象はカバレッジ実行器と関連テスト、E2E workflow、Android手引き・検証手順・残タスク、本記録。

比較条件の不一致を、現在のGradle実行後ではなく前に検出する。`run_coverage.py --preflight-only --base-ref <比較元>` はGitと公開設定だけを読み、既存のレポートを消さず、Gradle/SDK/エミュレーターを起動しない。最終E2Eの前に比較元と構成を確認し、通常のカバレッジ検証・E2Eを続ける。E2E workflowにも同じ事前検査を入れる。

受け入れ条件：

1. 比較対象がある場合の `TOOL_INPUTS` と既存の正規化・一致基準を再利用し、不一致では重い処理を開始しない。比較対象がない場合はその旨を区別し、従来不要だった比較を必須化しない。
2. 事前検査は有効な比較元を明示し、head/base・比較対象・設定ハッシュ・検査範囲を記録する。カバレッジ成功やE2E成功へ置き換えない。
3. 通常実行のclean・失敗記録・80%/低下判定と、比較元計測時の再確認を維持する。事前検査の成功で本検証を省略しない。
4. E2E CIでは比較元を入力で明示し、履歴取得後、JDK/SDK/エミュレーター準備前に検査する。Git refは環境変数から引用して渡し、式をシェルへ直埋めしない。
5. 事前確認後にソース・assets・設定・比較元を変更した場合の再確認を手順化する。Git/設定の検査は原子的な編集ロックや全依存解決の検証ではないと明記する。

検証は既存coverageテスト→実Gitの合成fixtureでRed/Green→全Pythonテスト→文書/差分・独立レビュー。Gradleはfixtureの偽コマンドで未起動を確認し、Androidや実E2E・CIは起動しない。現在の公開履歴への読み取り専用事前検査も行う。比較用モデル呼出し0回。実作業の再実行回数・時間/トークン削減は未測定として残す。

## 実装と検証結果

`run_coverage.py` に読み取り専用の事前検査を追加し、通常実行でもGradle前に比較対象と条件を調べる。比較元を実際に展開した後の既存の検査は維持した。比較対象の選び方・空行/coverage適用行の例外・80%/低下判定は変更していない。通常実行中に設定ハッシュや比較対象群が変われば失敗として記録する。

事前検査の結果は `mode=preflight` / `coverage=not-run`、head/base、比較対象、既存5入力と現在のcoverage設定のハッシュ。比較が不要な場合は検査済みとはせず、存在しない任意入力もnullで区別する。事前検査は古いレポートを消さないが、そのレポートの有効性を保証しない。通常実行のclean・失敗時のcomparison.json保存は維持する。

E2E workflowは `base_ref` 入力（既定 `origin/main`）を追加し、checkoutの全履歴取得後、JDK/SDK/AVD準備前に事前検査する。[checkoutの履歴取得](https://github.com/actions/checkout/tree/v4#fetch-all-history-for-all-tags-and-branches)と[dispatch入力](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onworkflow_dispatchinputs)の対応を確認し、Git refは環境変数から引用して渡す。必須 `verify` は変更しない。

主担当、Linux/POSIX・Python 3.13.16で次を実行した。全文ログと合成Git fixtureは公開対象に含めない。

| ID | 確認内容 | 結果 |
| --- | --- | --- |
| V1 | 変更前と変更後の既存 `test_coverage.py` | 各21件成功。80%・低下判定・レポート欠損・比較元失敗時の古いレポート除去を維持。 |
| V2 | 実Git fixtureの新規受け入れテスト | 未実装時6件・11アサーション失敗。実装後7件成功、実行中の比較群変更・比較不要時の任意入力欠落・イベント指定の拒否も加えて最終10件。5入力それぞれの不一致、未解決base、レポート保全、元の正規化、Gradle未起動と実行中の条件変更拒否を検証。 |
| V3 | 全Pythonテスト | `python3 -m unittest discover -s scripts/tests -q`、最終138件・失敗0・skip6（任意Kotlin解析依存なし）。既存WIPも含む作業ツリー全体の結果。 |
| V4 | 現在の公開履歴での事前検査 | base `46d5810`、head `28b6d5a` と作業ツリーで終了0、比較対象3ソース・conditions_checked=true・6設定ハッシュ・coverage=not-runを確認。Gradle/SDK/AVDは起動せず。実E2Eや今回CIの成功とは区別。 |
| V5 | 文書・差分・workflow | 対象5文書169ローカルリンクと `git diff --check` 成功。workflowの入力・引用・検査順をコード/公式資料と照合。ローカルYAMLパーサーは未導入で構文検証は未実行、GitHubでのdispatchも未確認。レビュー転記後も再確認済み。 |

合成fixtureでは偽Gradleの呼出痕跡を確認し、不一致の事前検査と通常実行のいずれでも一度もビルドを始めないことを検証した。事前検査が既存レポートやcomparison.jsonを変更せず、通常実行は古いレポートを消して失敗を保存することを別々に確認した。既存のアサーション・比較基準を緩めていない。

独立レビューで、初版の `--preflight-only --github-event` はPRイベント処理の `git fetch` を呼び、読み取り専用の契約に反するとの修正必須指摘（R01/R14）があった。事前検査を明示 `--base-ref` 専用に限定し、イベント指定をGit実行前に拒否するよう修正した。fake gitによる新テストでGit呼出ゼロ・終了2・レポート不変を確認し、通常のCIイベント処理は維持した。独立再確認でも指摘は解消済み。

## 判定と残る確認

主担当の判断は、事前検査・通常実行への前倒し・E2E経路の実装を完了し、通常作業で試行継続。今回差分は未公開でCI未実行、実Gradle・E2Eと新workflowの実dispatchは未確認。アプリ/Gradle設定・依存そのものは変更しておらず、ローカル検証はPython補助・実Gitの合成試験・読取事前検査に限定した。コミット・push・PR・CI起動は実施していない。

検査するのは既存の比較入力で、JDK/SDK・外部依存解決・全てのビルド入力や、ソース/asset内容の原子的な凍結は保証しない。設定と比較元を確定後にソース・assetsを変更しない手順、共通検証・E2E・APK同一性の確認を維持する。条件変更後は既存の再利用基準に従って必要範囲を再実行する。

保守担当は次の同種作業3件または2026-11-30の早い方で、後発構成変更の検出時点・E2E再実行回数・完了時間・全担当消費を同条件で確認する。実測前に過去147.208秒の再実行をそのまま削減保証へ換算せず、項目1・2の効果と合算しない。


## 独立レビュー

確認者：`review_ca001_004`（作成者と別agent）。基準 main/`28b6d5a`、今回対象8ファイルの未コミット差分を直接確認。既存WIPを保持。対象ファイルの編集、Git変更、実Gradle/SDK/E2E/CI起動、投稿、追加モデル実行は行っていない。独立テストは実Gitの合成fixture・偽Gradle/fake gitだけ。

### 対象版

| ファイル | SHA-256 |
| --- | --- |
| scripts/run_coverage.py | `566380b28078c27e31b33c6b359b4b34c54884d89b34040f1626729eccefc72a` |
| scripts/tests/test_build_preflight.py | `193cadd324141c70e9f696a4abf49877412bb732327f0c98e9378c891f7b6850` |
| .github/workflows/e2e.yml | `cbb8cba545e99f0a0bd8e9b68358586bdf129654c73a8f83893b8cb5afcc24cf` |
| docs/guides/android.md | `b29a109acd4b722c4ad0be5de0770fd96a6c2d29a0f341fd3a2dbfafabca4ab2` |
| docs/workflow/verification.md | `9843e9ddf3aa41377d145af396a97e4c4b4918372441b20cf5c0aab9dbbb27d4` |
| docs/guides/github-cli.md | `ee2cc141fb7d8f0bb112fa723f146c0c88024a4ed95dc01b2da40c3a08399f49` |
| docs/proposals/codex-adoption-remaining-tasks.md | `dbe60c3eb78d85766f33e62a273b974ed306755a1b4a5244c49fafdb75d3b45b` |
| docs/records/evaluations/2026-11-16-build-preflight.md | `e2a27d4fa5541b38d5a2c5de80f275f5a96862cf975f3b8b3995d93200218863` |

上記はF01修正・V2/V3更新後、最終レビュー転記前の版。

### 確認者の実行・根拠

- RV1（確認者自身）：既存 `test_coverage.py` 21件成功（0.005秒）。初版の新規9件成功後、F01修正後 `test_build_preflight.py` 全10件を実行し、失敗0（0.987秒）。アサーション緩和なし。
- RV2（確認者自身）：対象5文書のdocument_tools検証は169ローカルリンク成功、`git diff --check` 成功。F01/V2/V3の記録更新後も再実行して同じ成功を確認。
- RV3（確認者による保存結果/版照合）：主担当の最終全suiteは138件失敗0skip6、summary passed/0。主担当の実repo事前検査は比較3ソース/6hash・mode=preflight・coverage=not-runを記録。確認者の実repo検査再実行ではない。verify workflow/title validator/80%・低下validatorはHEADとバイト一致。前レビューのwait/コメント補助等7ファイルのハッシュ不変を確認。
- RV4（直接読取）：checkout直後に全履歴→引用したenv入力の事前検査→通常のJDK/SDK/AVD/Gradleというworkflow順序を確認。失敗後に重い準備へ進むalways/continue-on-errorはない。[checkout@v4](https://github.com/actions/checkout/tree/v4#fetch-all-history-for-all-tags-and-branches)と[dispatch入力の公式資料](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onworkflow_dispatchinputs)を直接照合。YAMLパーサー検証と実dispatchは未実施。

### 指摘と再確認

F01（初回R01/R14・修正必須、解消済み）：初版は `--preflight-only --github-event` を許し、PRイベントの `resolve_base` がgit fetchを呼んだため、read-only契約に反した。確認者がfake gitだけで終了0/fetch呼出を再現し、実通信・Git更新は行わなかった。

作者がpreflightを明示 `--base-ref` 専用に限定。`--github-event` 単独との併用をGit実行前に終了2とし、従来の通常CIイベント経路は保持した。新テストでGit呼出ゼロ・元report不変・Gradle未起動を固定し、確認者が修正後10件を独立実行して成功。記録V2/V3と指摘対応の追記も直接再確認した。

### R01〜R30

| ID | 判定 | 根拠・理由 |
| --- | --- | --- |
| R01 | 確認済み | F01修正後、preflightは明示baseのGit/公開設定読取だけ。Gradle前の既存比較条件検査とE2E前倒しをRV1〜RV4で確認。 |
| R02 | 確認済み | 不一致/不明base/必要入力欠落を失敗とし、比較不要・任意入力欠落はfalse/null。設定/比較群の実行中変更とイベント指定拒否もテスト。 |
| R03 | 確認済み | Linux/Python3.13.16、既存5比較入力と現在coverage設定、checkout@v4を維持。verify/validator/80%基準はHEAD同一。 |
| R04 | 確認済み | 今回8ファイルと既存WIPを区別。前の待機/コメント補助等7ファイルのハッシュ不変、既存提案と他の作業保持を確認。 |
| R05 | 確認済み | RV4の公式checkout全履歴/dispatch string入力を確認。実Gitの既存rev-parse/show/diffを合成fixtureで実行。実dispatchは未確認。 |
| R06 | 確認済み | 構成検査・カバレッジ本検証・E2Eを分離し、過去147.208秒の再実行を削減保証へ換算しない。 |
| R07 | 確認済み | UTF8設定・SHA256・bool/nullと比較不要を区別。正規化は元の空行/APPLY除外だけ。source集合を同じ定義で固定。 |
| R08 | 確認済み | context→事前条件→Gradle→入力/群再確認→従来base計測/再確認→閾値/低下判定の流れを追跡。 |
| R09 | 確認済み | 既存実行器へ集約し、アプリ/Gradle設定や比較ロジックを改変しない。手順は正本verificationと実行guideへ配置。 |
| R10 | 確認済み | 既存Git・正規化・比較処理を再利用。新依存や独自比較基準、監視基盤を増やしていない。 |
| R11 | 確認済み | preflightはreport非変更、通常実行は古いreport除去と失敗JSONを維持。6hash/比較群の実行中変更を拒否。原子的編集ロックではないと明記。 |
| R12 | 確認済み | 従前の公開利用者確認範囲を継承。公開コード/設定・合成Git/fake Gradle・必要集約と公式資料のみ。私的資料や認証情報の探索/転載なし。 |
| R13 | 確認済み | 公開対象はコード・合成テスト・手順・集約。ローカル生ログ/個人設定や私的パスを追加していない。 |
| R14 | 確認済み | F01解消。refはenvから引用、解決時end-of-options、解決後SHAでshow/archive。preflight+github-eventはGitを呼ぶ前に終了2。 |
| R15 | 対象外 | 新規外部依存・第三者素材の導入なし。checkout@v4も既存版。 |
| R16 | 確認済み | 固定設定/既知source/旧report、5条件ごとの不一致、例外APPLY/空行、Gradle sentinelを期待値として定義。 |
| R17 | 確認済み | 独立既存21件/修正後新規10件が成功。Git fixtureと偽Gradleだけで受入・異常・保全・変更拒否を確認。 |
| R18 | 確認済み | 不一致通過・Gradle先行・report消去・条件緩和・途中変化無視・fetch許可という誤りを具体的アサーションで検出。 |
| R19 | 確認済み | RV1/RV2は確認者の実行。全138件/実repo事前検査は主担当の保存結果を直接照合し、確認者再実行とはしない。 |
| R20 | 確認済み | 主担当138件失敗0skip6を確認。新workflowのYAMLパーサー/dispatch、実Gradle/E2E/今回CIは未確認と明示し、事前検査を成功の代用にしない。 |
| R21 | 確認済み | 日本語手順/UTF8・Git refと比較対象パスを扱い、不要な文化的制約を追加しない。 |
| R22 | 対象外 | アプリUI・アクセシビリティ変更なし。 |
| R23 | 確認済み | mode=preflight/coverage=not-run、conditions_checked=false、6hash/nullと失敗後の必要な再検証を説明。 |
| R24 | 確認済み | 実行器/新テスト/1workflow/5文書の一つの目的。既存WIPを保持し、必須verify変更を混ぜない。 |
| R25 | 確認済み | RV2/RV4：5文書169リンク、CLI/guide/workflow入力・実装整合とcheckout直後の順序を確認。 |
| R26 | 確認済み | 実作業再実行削減・消費・時間は未測定。Git/設定検査の範囲を限定し、性能改善や依存解決完了を保証しない。 |
| R27 | 確認済み | 通常runのclean/失敗記録/閾値と比較を維持。preflightは古いreportを保つが有効性を保証しない。条件変更後の再利用見直しを明記。 |
| R28 | 確認済み | 実装完了/試行継続と実CI未確認を区別。ローカル検証の採用可をdispatchや全入力凍結の保証へ広げない。 |
| R29 | 確認済み | 初回修正必須F01は作者修正と独立再確認で解消。保守担当/同種3件または11月末の見直しを明示。 |
| R30 | 確認済み | 重い実行前の不一致検出とreport保全に価値を限定し、共通検証/E2E/同一APKの確認を省略しない。 |

### 指示書保守の確認（R01〜R30とは別）

1〜17：確認済み。正本はverification、具体コマンド/取得範囲はAndroid/gh guide、根拠と採否は評価記録へ配置。実行条件・対象base・失敗停止・公開区分・比較不要/未計測・再利用条件・必須検証維持と参照実在を確認した。18：確認済み。旧SDK/E2Eコマンドを段階実行へ変更したが、SDK/AVD構成とE2E本体・共通検証は維持し、条件不一致や後発変更時の再確認を明記。19：対象外（文書移動なし）。

### 総合判定・残る確認

F01は解消、修正必須の残存なし。**採用可（ローカル検証済みの実装・手順とworkflowの静的確認範囲）**。今回差分のCI・YAMLパーサー検証・実dispatch・実Gradle/E2Eは未確認であり、この採用可を統合に必要なCIや端末確認の代用にしない。

Git/公開設定の検査は全依存解決・全入力列挙・原子的な編集ロックではない。保守担当は次の同種作業3件または2026-11-30の早い方で、検出時点・E2E再実行・完了時間・全担当消費を確認する。通常の共通検証/E2EとAPK同一性の保証、失敗・未取得値を維持する。

主担当の転記後確認：8ファイルの転記前ハッシュ一致を確認。以後の変更は本記録の検証結果表記とレビュー転記だけで、実装・テスト・workflow・既存WIPに変更なし。文書・リンク・差分を転記後にも再確認済み。
