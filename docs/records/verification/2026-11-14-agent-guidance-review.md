# agent 指示書・参照文書再構成の独立レビュー

## 対象と確認者

作成者は主担当 agent、確認者は別担当の `review_guidance` agent。表記修正以外に文書の責務と取得ツールを変更するため、セルフレビューの例外を使わず独立レビューを行った。確認者は対象を編集せず、本記録だけを作成した。Git の読取操作以外にコミット・push・GitHub 操作は行っていない。

対象は `docs/reorganize-agent-guidance`、HEAD・比較元 `e43d080` からの未コミット差分と未追跡の新規公開ファイル。ステージ済み差分はない。既存の未追跡ドラフトの移動を含む。目的・受け入れ条件・配置判断・作成者の実行結果は[作成者記録](2026-11-14-agent-guidance-reorganization.md)を直接確認した。既存パス維持を求めない再構成と `app-spec.md` の名称指定は依頼者から共有された利用者条件である。

初回の対象103パスの集約 SHA-256 は `8f541a6ea29078e3c6afed767850b8c4952784cdb625c882793774d0f3275160`。初回指摘に対する修正と最終記録更新後、対象は123パスとなった。末尾に最終のファイル一覧とハッシュを記す。本記録自身は対象集約から除外する。

## 直接確認した根拠

実行者は確認者、環境は作業環境の Python 3・Git。作成者の検証結果を成功の代用にせず、以下を独立して確認した。

| ID | 確認・コマンド | 結果 |
| --- | --- | --- |
| E1 | `git status --short`、ブランチ、`git log -3 --oneline`、`git diff e43d080`、`git diff --cached`、`git ls-files --others --exclude-standard` | 比較元とHEAD一致。未追跡の新規公開文書を含め、末尾の対象に固定 |
| E2 | 旧開発・Git・Android・探索手引きと分割後本文の段落をリンク表記等を正規化して比較し、差分を読解。レビュー基準行と旧保守チェックを個別照合 | R01〜R30本文30行が全件バイト一致。旧保守チェック15件をすべて保持。閲覧動作・制約、許可範囲、必須検証・レビューの要件を移動後に確認 |
| E3 | `python3 -m unittest discover -s scripts/tests -q` | 終了0、98件実行・失敗なし・6件skip。任意のKotlin構文木環境を使う6件は未実行 |
| E4 | 追跡済み・非除外の未追跡Markdownの現存パスを明示した `python3 scripts/document_tools.py check <paths...>`、`git diff --check` | 修正後・本記録追加前は61文書378ローカルリンク成功、空白エラーなし。本記録追加後も62文書382ローカルリンク成功（終了0）、差分確認成功 |
| E5 | `python3 scripts/document_tools.py context change --include docs/guides/agent-tools.md document-tools check-output`、`context review`、`read docs/project/app-spec.md 現在の動作` | 全て終了0。contextは6文書から取得しR01・R30を含む。change実例23,095文字、review16,100文字、仕様節812文字。重複排除・範囲再利用・不正入力・原子性はE3の既存テストも照合 |
| E6 | `docs/project/architecture.md` を `ReaderViewModel.kt`、`DocumentSource.kt`、`ArchitectureTest.kt`、ビルド設定と照合 | 責務、依存方向、IO実行、キャンセル、資源解放と保証の限界の説明が対応。新規API・依存・CI設定なし |
| E7 | 移動前のJSON10件を `git show e43d080:<旧パス>` で取得し、`docs/records/evaluations/` の移動先とバイト比較。記録本文の公開JSONパスを列挙し存在確認 | 10件全てバイト一致。修正後のMarkdown内のJSONパスは全て実在。固定データの旧入力パスを現行手順へ読み替えない説明も確認 |
| E8 | 同リポジトリ `blob/main` の絶対URL3件は作成者記録V8とテンプレート原文・現行正本を照合 | 参照するファイル・アンカーが現在の配置に存在。外部URLの到達性や統合前のmainへの反映は未検証 |
| E9 | [既存利用者確認](../evaluations/2026-11-07-instruction-reading.md)末尾と[継承記録](../evaluations/2026-11-14-adoption-remaining-tasks.md)の再確認節を直接確認 | 同じ既存環境・公開文書・必要な差分・合成入力の範囲で継承。別サービス・私的資料の共有許可へ拡張せず、保存・入力利用条件の監査済みとはしない |

分割前資料・過去記録の正規化比較は、移動と参照置換以外の変更を絞る補助であり、リンクの意味の正しさや実際の過去実行を証明するものではない。初回のJSON欠落も、Markdownリンク検査だけでは見つからず原文と実在パスの照合で発見した。

## R01〜R30の判定

以下は指摘修正後の最終判定。初回指摘と対応は次節に保持する。

| ID | 結果 | 根拠・理由 |
| --- | --- | --- |
| R01 | 確認済み | 作成者記録の受け入れ条件とE1・E2。AGENTSは入口、projectは事実、workflowは規則、guidesは実行方法、recordsは根拠、proposalsは未採用案として配置 |
| R02 | 確認済み | E3・E5。取得失敗・欠落・曖昧な節・上限超過・state失敗の既存テストを維持。アプリの取消・再選択・失敗時の要件もE2で保持 |
| R03 | 確認済み | E2・E6。Python標準機能と現行パス・アンカーを照合。Android設定・CI定義は変更せず、移動した版やコマンドは既存定義と対応 |
| R04 | 確認済み | E1・最終対象一覧。未追跡の公開ファイルとJSON移動を含め対象固定。ドラフト本文・配置を確認し移動方式を作成者へ確認。事前ハッシュ不在の制約は後述 |
| R05 | 確認済み | E3・E5。新たなAPI・パッケージはなく、変更したローカルコマンドの取得先・実行例は現物と実行結果で確認 |
| R06 | 確認済み | E2・E6・E7。仕様・構造とコードを照合。初回のJSON根拠パス欠落は修正後に解消。速度・使用量の削減効果を保証していない |
| R07 | 対象外 | 新規技術・言語変換・デコード方式の変更なし。取得先分割に伴うUTF-8文書取得はE3・E4で確認 |
| R08 | 確認済み | E2・E5。正本分離とcontextの選択先を説明でき、共通事項が6文書から原文取得されることを確認 |
| R09 | 確認済み | E2・E6。現在の仕様・構造と設計変更時の判断を分離し、アプリの既存責務境界は維持 |
| R10 | 確認済み | docs/README.mdとE2。文書区分・専用様式が役割に対応し、skillsやPRテンプレートへ基準本文を重複させない |
| R11 | 確認済み | E3・E5。contextの入口から文書選択・取得・出力まで追跡。state更新・失敗時の原子性の既存テストを維持。アプリの非同期処理は変更なし |
| R12 | 確認済み | E9。今回も同一の既存環境と公開資料に限定。既存利用者確認の適用範囲の継承であり、利用条件の独立監査ではない |
| R13 | 確認済み | E1・E2・E7。非除外の公開対象・差分のみ確認し、ローカル専用資料を取得・転載していない。JSONは既存公開blobと同一。公開操作前のステージ・履歴確認は実行者が別途行う |
| R14 | 確認済み | E3。取得先変更で許可・ファイルアクセス境界を変更せず、除外対象・リポジトリ外入力の拒否を既存テストで維持。アプリURI処理は変更なし |
| R15 | 対象外 | 新規依存・外部コード・画像等の素材を導入していない。既存公開JSONはバイト無変更の移動 |
| R16 | 確認済み | E2・E3・E5。テストの期待値は必須共通節・R全件・原文ハッシュ・重複排除という仕様から定義。新構成の文書分担に合わせfixtureを更新 |
| R17 | 確認済み | E3〜E5・E7。本文保持・正常取得・入力エラー・文書リンク・JSON証拠の存在を適切な層で照合 |
| R18 | 確認済み | E3とtest_agent_tools.py差分。R01とR30・全マーカー、原文ハッシュ、失敗時stdout/state不変の期待値を維持。件数増加は文書分割に対応しアサーション緩和ではない |
| R19 | 確認済み | E3〜E5・E7。コマンドと結果を独立確認し、skipを実行済みに含めない。Python実装変更後の再実行で不具合を隠していない |
| R20 | 確認済み | ローカルPython・文書検証とCIを区別。Android本体・設定・利用経路は無変更のためAPK・E2Eは対象外。push・PRなしでCI未実行。公開・統合時は対象コミットの必須CIを別途確認 |
| R21 | 確認済み | E3〜E5。日本語見出し・明示アンカーを含む原文取得とリンクが動作し、新たな言語・日時・入力の制約を追加しない |
| R22 | 対象外 | アプリUI・操作・支援技術との接続を変更しない。文書移動からアクセシビリティ検証済みとは主張しない |
| R23 | 確認済み | E2・E5。現在の仕様、開発者の入口、失敗時の次の操作と未実装事項を区別。commit検証の規約表示先も実在する正本へ更新 |
| R24 | 確認済み | E1・E2・E7。多数のファイルを扱うが一つの文書再構成に限定。段落保持比較・JSON無変更比較と経路の直接確認により対象全体を確認 |
| R25 | 確認済み | E3〜E8。skills、テンプレート、取得ツール、例、テスト、相対・絶対参照を照合。JSONとCI説明先の初回指摘も解消 |
| R26 | 対象外 | 性能・使用量・時間の定量改善を主張しない。効果未計測と次の評価契機を作成者記録に明記 |
| R27 | 確認済み | E1・E7。利用者条件で旧パス維持は不要。現行参照を更新し、固定JSONと既存記録の根拠を保全。アプリ保存形式・配布・外部サービスは変更なし |
| R28 | 確認済み | 文書の責務を明確にする利益と、移動範囲・既存外部参照の負担を区別。E9の範囲外の条件監査や、未計測効果への判断を広げない |
| R29 | 確認済み | 下記F1・F2を修正必須と改善提案に分け、作成者の修正後にE4・E7と参照先を再確認。残る制約・担当・確認契機を下記に記録 |
| R30 | 確認済み | AGENTSから必要な正本へ進め、現行の規則・仕様・実行方法・過去根拠が区別される。生成量ではなく要件保持と保守上の役割を根拠に評価 |

## 指摘・対応と再確認

| 指摘 | ID・重要度・ファイル行 | 条件・影響・修正案 | 対応・再確認 |
| --- | --- | --- | --- |
| F1 | R06・R25、修正必須。初回の `docs/records/evaluations/2026-11-13-adoption-remaining-comparisons.md:85`〜88、`2026-11-13-codex-adoption-followup.md:119`、`2026-11-14-adoption-follow-through.md:60`・62・63 | JSON10件が旧ディレクトリに残る一方、Markdownの証拠パスだけ新ディレクトリへ書き換えられ根拠を辿れない。Markdownリンク構文でないのでリンク検査が成功しても残る。JSONを実際に分類先へ移し参照をそろえるか、実在パスへ記載を戻す | 作成者が10件を records/evaluations へバイト無変更で移動、Markdown参照とrecords説明を更新。E7で基準blobと全件一致・公開JSONパス実在を確認。解消 |
| F2 | R25、改善提案。`docs/workflow/git.md:196` | CIの実行範囲・拡張方針の正本がverificationへ分かれたが、リンクはdevelopmentのまま。現状も辿れるが正本への直接参照にすると役割が明瞭 | 作成者が `verification.md#必須-ci-とブランチ保護` へ変更。本文・参照先・E4を再確認。解消 |

修正は確認者が行っていない。追加差分はJSON10件の移動、評価・検討記録のJSON参照、Gitの参照先、recordsの説明、作成者検証記録の更新。R04・R06・R13・R19・R24・R25・R27・R29を重点的に再確認し、その他は対象本文・Pythonコードのハッシュ不変を確認して初回根拠を継承した。

## 制約・残るリスクと判定

- 既存未追跡ドラフトは移動後本文を直接確認し、作成者から本文を編集せず移動した手順と、唯一のローカルリンクが移動前後で同じ深さにあることを確認した。事前の内容ハッシュ・独立保存コピーがないため、確認者が移動前後のバイト一致を独立に証明したとは扱わない。作成者説明と移動後原文の範囲で保全を確認し、欠落を示す事実は見つからない。追加の異同が問題になった場合は保守担当が利用者の原本と照合する。
- パス移動による公開済み外部参照への影響は、旧パス維持を求めない利用者条件に従う。リポジトリ内参照は本レビューの範囲で確認した。将来のリンク切れ報告は保守担当が対応する。
- Kotlin構文木用の任意環境の6件は未実行であり、今回その処理は変更していない。環境・当該処理を変更する際に保守担当が実行する。Android・CI・E2Eの保証を本レビューで追加したとは扱わない。
- 所要時間・全担当の使用量・保守負担の改善効果は未計測。次の同種作業で保守担当が既存の評価手順に従い判断する。

修正必須の残存指摘はなし。総合判定は **採用可**。対象と確認範囲に対するagentレビュー結果であり、GitHub承認・必須CIの成功・外部利用条件の独立監査を意味しない。

## 最終対象の識別

対象は123パス。各行をパス順に `path + NUL + sha256-or-deleted + LF` としてUTF-8連結した集約 SHA-256 は `4ea708fce7f1f7c8894147a46c8e4750eb283823ccb7d5c417efc7887d1b30e0`。本記録自身は除外する。以下はそのハッシュ入力の可読表現である。

```text
.agents/skills/review-changes/SKILL.md de66559e14f3d2fc1379f23cfd057a43758411d8791421a6787ef7831797a475
.agents/skills/verify-changes/SKILL.md 6db2d298e2137a255fa0ae6889487dd5cdf7795141dcbfe642d9273b82683ebf
.github/pull_request_template.md 778f26e793e2378f976312c541b5ac381b5e2cc7cf9831592399e18b07072ada
AGENTS.md ef2c5719392d19ce2107d99d04c3fdc84dd43defca2f0d89450f56f9513322a2
README.md 64683c021faaae27b9e19574d342d064cea648a387863ddc3682de54e5439d4f
docs/README.md b8cdb65f353194a3a9c6c83755dae35f3656fc1df4916647b9978d187ccc080a
docs/agent-search-tools.md deleted
docs/android-build.md deleted
docs/development-workflow.md deleted
docs/git-workflow.md deleted
docs/guides/agent-tools.md ddf4c6c55dc25e3dd6acf32cb01fe221a3e34ac55eba069bafc5cddfcc9a2010
docs/guides/android.md 3e79b8419f266ca791fc0bd9644c22c964119c3372b85c117be19e9699afa6f6
docs/guides/github-cli.md 74493c162a6384e3183a8f8e2c9d107584c10c763089134c59740c0c9b9f8528
docs/maintenance/agent-instructions.md e1d64b6204fda1fb2836ab952030755585d4b23909210b64b2a25e7c63b737d3
docs/maintenance/dependencies.md 339b545ffb8db7ce7bf0a952a02dd38ae8ab94da8c938bffe734407a2310bee9
docs/maintenance/evaluation.md e68f2ce06afb67130ddad025aac4dc22f7eff2be0345a68c30ef82e68c6b6f5b
docs/notes/agents-md-checklist.md deleted
docs/notes/codex-adoption-recommendations.md deleted
docs/notes/codex-adoption-remaining-tasks.md deleted
docs/project/app-spec.md cd6e6c311832db1f9c99643a69c2427c3d3a148eb450fd57371007980b0aabd1
docs/project/architecture.md d9cb594fac2bd64a4a6320b08cf35fece3df17af0d498cdffe27a689e7590176
docs/proposals/README.md 3f5c3945c1216522315a0610b8d74c75fb61fc9ded364cafcdcff5b5e761fa28
docs/proposals/agents-md-draft.md 4f68586f7b30cb9d5bd0b2e1aa3f06d3fa1eaee44835769a497f59773c6dbc93
docs/proposals/codex-adoption-recommendations.md ec82379ce235f0721e9c8d05eb282bc56183c9d08e9383c5e72e59ff5cd78b09
docs/proposals/codex-adoption-remaining-tasks.md e5890f47d8c2bf37686ffa4a9f285292c1a0444d0ae035ab4df77a13bb5368e2
docs/records/README.md f58a042953402660461f80809fe4b630e251e400f72036562d17840383f045ca
docs/records/evaluations/2026-11-03-agent-context.md 9d43a54266304fbd198d5b3f7eb9f9262b30ab781e2b1b52857aa58a8c7c7b35
docs/records/evaluations/2026-11-07-instruction-efficiency.md ab9084527c8ee04f1fa4a5266938073c13e4822ad55377b6a93e553b31f0bb33
docs/records/evaluations/2026-11-07-instruction-reading.md 6958c03cedcddc22937112a1bb7efecabcbb3142a4145b8fd833e09bf3d03734
docs/records/evaluations/2026-11-11-agent-tools-eval.md 11852b772b24cef03abdc088ab46629e4075bb01fa4d40b77487ed319f4b0317
docs/records/evaluations/2026-11-12-agent-context-evaluation.md 1166472f8412163fae685aa443b6a1368b2ac3d68b2e94f79adc386d6bd54d9b
docs/records/evaluations/2026-11-12-codex-adoption-evaluation.md fefcb85b95c2c5be2c6ac5adb50ec9d85efccaf46fd3fb0dcc2f063cd378f70d
docs/records/evaluations/2026-11-12-codex-adoption-medium.md 89398eb638ec2dc907f3c72977f8f61dab13ac80854a7d3389948742bf16e452
docs/records/evaluations/2026-11-12-codex-adoption.md fa0f9306cf55876204f7792b41a75b6167c6742acadd3d4a8490c9df72e1b569
docs/records/evaluations/2026-11-13-adoption-comparison-protocol.json 671c091bd6902c86b4947823f2f0bc7c018be60abd64f4f9728cd484fd6f812f
docs/records/evaluations/2026-11-13-adoption-remaining-comparisons.md 2a92d905ffdfe63346544b311a1c95dbe630bf1459f9eb5fa82b376de9f7c70b
docs/records/evaluations/2026-11-13-adoption-remaining-results.json 6d840117723550a220d56d45b9c1c4364085e3b808467eecc507db128e712c2a
docs/records/evaluations/2026-11-13-codex-adoption-followup.md 2eb472cc686adf9564c548d6cbf5d40cc577f74e1e3e9490e6137d9644a6d45a
docs/records/evaluations/2026-11-13-compaction-protocol.json b19555b26765d86253aa1b301af31c04682ddf86dd0af30e4ab1222f46c27334
docs/records/evaluations/2026-11-13-model-output-phase2-protocol.json 221697476f875aa8b60de76022ec7e77194eb3389e413eb5a30acb6d32c04351
docs/records/evaluations/2026-11-13-model-output-protocol.json e056b926ebe30a284ad529be26ef20e7869d976c6540739957ee7cbcb5429f50
docs/records/evaluations/2026-11-13-verbosity-implementation-protocol.json 5b0d62d0887e43a7436083b9bf2e0b7bfdb965f445392de0e0a6007255084d85
docs/records/evaluations/2026-11-14-adoption-follow-through.md 2c88e03d860dd484302ec0954156e69ad5ae3d1360941f53a26959c059a0dc79
docs/records/evaluations/2026-11-14-adoption-measurement-coverage.json 4274428cd0164a33f6e890dec442823eaa1829dd23ead89bfe3fc8630776c795
docs/records/evaluations/2026-11-14-adoption-remaining-tasks.md 36550ae800caced74438d46682bbaf45a584329fd03062cc1885c4f3c697d28b
docs/records/evaluations/2026-11-14-context-read-reuse.md 29c6b7549f39268ce9d312b49e7cba0ac5dc2103f666c59b44b22c91af7eea7c
docs/records/evaluations/2026-11-14-context-token-evaluation.md a0a84e9c7e35e1e739c0adeacc47ae3055d7d597ab23c1ac1430606dbc9158c3
docs/records/evaluations/2026-11-14-context-token-protocol.json 724d3aca1f62ae41ce1122b903e4fa9347388e266e177f17166eadf0e2ba1f43
docs/records/evaluations/2026-11-14-context-token-results.json 31a54e498c03902bae0bde4736d27b837be265c0b447c12f654edb75c01cf143
docs/records/evaluations/2026-11-14-verbosity-implementation-results.json 4a2a1543eef284d1b9cf6d44cc1f5d7a3b893368208d8e1aebcf72bce94bae3b
docs/records/verification/2026-11-01-branch-protection.md 446395fde5f1c6398978037ddce734a2e647dec08569b2aeaa55371543ba3039
docs/records/verification/2026-11-01-code-review.md 15c090c93b90b80e2b349630194d7838604598fb6f103c5f39d67c00aaed1b4f
docs/records/verification/2026-11-01-initial-implementation.md e28a0a804a21abc0c6b579d0c143c2a550a8b44aa48b018e48721a084dbfc697
docs/records/verification/2026-11-02-git-hooks.md 5f1348cc89eed67472495e5db1f1d2b9c59df9802e12f3c1d69d64a2d82c82d7
docs/records/verification/2026-11-03-agent-planning-pilot.md 6b75dfbe2cd80916038f7a4e98fcc223e9d71d639a7335033dbc5b69cdc0dbeb
docs/records/verification/2026-11-03-architecture-checks.md 568a18522b9f1523183c49db92e16a0228928f2ab8b62f81331d0e39acbca9df
docs/records/verification/2026-11-03-codex-skills.md 82c35f5ddbc36179bc2b1b9d463e76c692bd56534e8899d8d2c9ec4b3740e1fc
docs/records/verification/2026-11-03-coverage.md 7a492ff96ce1cb353cdbe39f2f52514718bfad43868f03af9d73465db5bdc54d
docs/records/verification/2026-11-04-mutation-tests.md f243945b3a9d990f3fb45eb0944a3a564cf6019e2dbda7ade8cec3ff8922c69a
docs/records/verification/2026-11-04-property-tests.md c26031e2502bad405999764662de66e2151e336f91a84850e5ac7703f10c4524
docs/records/verification/2026-11-05-e2e-ci.md 04196d25a62985aaa65fb359f6591b3e3aed4719174d5212fe4dea75b2b904f0
docs/records/verification/2026-11-05-e2e-expansion.md fa748242bd761d22c13f7ff512b05120a88f5fcf03e433d45c6d7f4ecdadbca3
docs/records/verification/2026-11-05-e2e-tests.md da15dfea496e5c4e0f09fa82b9cbc7dbaa065ed805315c968b5caebc50940ce3
docs/records/verification/2026-11-05-e2e-workflow.md 59ca0a719894baf78598ac95db3f7bddc6844babdd4121e906adeadd60c7e2e2
docs/records/verification/2026-11-05-touch-targets.md b54f688f89c48a130141048e16e652cc13284e1dc9be597dfe4d66ef1f2b4a0a
docs/records/verification/2026-11-07-github-cli.md 8a327b4ea3abf7fc6ca0a9d054b20d3f9eea9b87f908e87de6eca56d55ae6db5
docs/records/verification/2026-11-11-agent-tools.md 468dcdc1fe1fcfe590d56f36343acf2a916a49458e30aa73e91859754d6a50c9
docs/records/verification/2026-11-14-agent-guidance-reorganization.md 83bc00308c2ca147f3024ed7c6e488f66054baa8561644df945a385e509ae37d
docs/templates/agent-handoff.md deleted
docs/templates/codex-adoption-evaluation.md 2d26f748b8f0829feea5864827d38b1e2a831a3fe35fac3c1501666c337d8638
docs/templates/handoff.md a7f27dcde047885db989ef49f8c310a8870b54061794bb856556df58c75e7813
docs/templates/implementation-plan.md b12484b87b080c8e83f03134517a51f7dfccdf99b6eb416b861061339045d4e9
docs/templates/review-record.md bc691ec5411a398b957cbf4d14281c9104dcb93acd1b6551035a6d8391fc3d22
docs/verification/2026-11-01-branch-protection.md deleted
docs/verification/2026-11-01-code-review.md deleted
docs/verification/2026-11-01-initial-implementation.md deleted
docs/verification/2026-11-02-git-hooks.md deleted
docs/verification/2026-11-03-agent-context.md deleted
docs/verification/2026-11-03-agent-planning-pilot.md deleted
docs/verification/2026-11-03-architecture-checks.md deleted
docs/verification/2026-11-03-codex-skills.md deleted
docs/verification/2026-11-03-coverage.md deleted
docs/verification/2026-11-04-mutation-tests.md deleted
docs/verification/2026-11-04-property-tests.md deleted
docs/verification/2026-11-05-e2e-ci.md deleted
docs/verification/2026-11-05-e2e-expansion.md deleted
docs/verification/2026-11-05-e2e-tests.md deleted
docs/verification/2026-11-05-e2e-workflow.md deleted
docs/verification/2026-11-05-touch-targets.md deleted
docs/verification/2026-11-07-github-cli.md deleted
docs/verification/2026-11-07-instruction-efficiency.md deleted
docs/verification/2026-11-07-instruction-reading.md deleted
docs/verification/2026-11-11-agent-tools-eval.md deleted
docs/verification/2026-11-11-agent-tools.md deleted
docs/verification/2026-11-12-agent-context-evaluation.md deleted
docs/verification/2026-11-12-codex-adoption-evaluation.md deleted
docs/verification/2026-11-12-codex-adoption-medium.md deleted
docs/verification/2026-11-12-codex-adoption.md deleted
docs/verification/2026-11-13-adoption-comparison-protocol.json deleted
docs/verification/2026-11-13-adoption-remaining-comparisons.md deleted
docs/verification/2026-11-13-adoption-remaining-results.json deleted
docs/verification/2026-11-13-codex-adoption-followup.md deleted
docs/verification/2026-11-13-compaction-protocol.json deleted
docs/verification/2026-11-13-model-output-phase2-protocol.json deleted
docs/verification/2026-11-13-model-output-protocol.json deleted
docs/verification/2026-11-13-verbosity-implementation-protocol.json deleted
docs/verification/2026-11-14-adoption-follow-through.md deleted
docs/verification/2026-11-14-adoption-measurement-coverage.json deleted
docs/verification/2026-11-14-adoption-remaining-tasks.md deleted
docs/verification/2026-11-14-context-read-reuse.md deleted
docs/verification/2026-11-14-context-token-evaluation.md deleted
docs/verification/2026-11-14-context-token-protocol.json deleted
docs/verification/2026-11-14-context-token-results.json deleted
docs/verification/2026-11-14-verbosity-implementation-results.json deleted
docs/workflow/design.md 1e5204caae9795d935d3c8dfa4257c862b25b64f456b455c99064d6afe33bcac
docs/workflow/development.md 76f07245eebe1d1d923fd9699d042b0363f944cb18347ebb40b16d30f62eb301
docs/workflow/git.md 1bec7eabe2ae0220a2db3363e1e50849e180164a8fc2664e705f45f935bb7c9c
docs/workflow/release.md 960abb1eecf14597c3c0a71f8c838f4825f302b1e9f7019d4003fd14eacb45af
docs/workflow/review.md 922dcc738a4c6f090d742d600feba357282136ac105a5a92abd05cfd898d5a2c
docs/workflow/verification.md 12ca2025f740d5cc2517068a4858417f57d25d807b1273c45393a646e5e17ab5
scripts/check_commit_message.py de7cb86756987c591b4808dc9ecda2483d92b5dff5517ef69a4c4bb82549cca1
scripts/document_tools.py baccf6f07906c0e7fce4a7ddba0fe31e68c3919d1fc7b00ae9403bd3fc163c5d
scripts/tests/test_agent_tools.py 76f5fc79d762918048776a773963293d078d64ad19af2b1830698474146f8f8e
```
