# プロパティベーステスト導入記録

本書は公開前の実装・ローカル検証・別agentレビューの記録である。
初回はコミット・pushの依頼がなくCIを未確認とした。その後、利用者の追加指示を受けて
公開・CI確認・統合まで進める。対象コミット、PRと統合後mainのCI run、成果物、
R20の再確認と最終判定は [PR #21 の最終確認記録](https://github.com/nagayasuu/org-mobile-android-sample/pull/21)
へ集約し、以下の初回時点の判定とは区別する。

## 目的・受け入れ条件・計画

README の課題2に対応し、既存 JUnit 4 の具体例テストを保ちながら
`OrgParser`・`DocumentDecoder` に Kotest Property を導入する。
6つの性質を各1,000例、上限のある公開可能な合成入力で検証する。
1件の反例で失敗し、seed と縮小入力を記録して再現できることを条件とする。
本番コード、UI、ファイルアクセス、状態管理、ミューテーションテストは変更しない。

1. 既存の解析・デコードテストで基準を確認する（V1）。
2. テスト依存、共通生成器、6つの性質と seed の指定を追加する（V2）。
3. 意図的な反例の検出・同一 seed の再現を確かめ、一時変更を撤去する（V3）。
4. 共通検証・カバレッジ・文書を確認し、別 agent に R01〜R30のレビューを依頼する（V4以降）。

## 対象・環境・採用理由

- 作成・検証者：主担当 Codex agent。
- 比較元：`022af30`、ブランチ `test/property-based-tests` の未コミット差分。
- 対象：`app/build.gradle.kts`、`PropertyInputs.kt`、`OrgParserPropertyTest.kt`、
  `DocumentDecoderPropertyTest.kt`、README、本記録、開発手順、ビルド・検証の手引き。
- 環境：Linux、Temurin JDK 17.0.21、Gradle 9.4.1、AGP 9.2.1、内蔵 Kotlin 2.2.10、
  Android SDK Platform 37.0 / Build Tools 37.0.0、coroutines-test 1.10.2。
- [Kotest 6.2.6](https://github.com/kotest/kotest/releases/tag/v6.2.6) を固定。
  [配布 POM](https://repo.maven.apache.org/maven2/io/kotest/kotest-property-jvm/6.2.6/kotest-property-jvm-6.2.6.pom)で
  Kotlin 2.2.21・coroutines 1.10.2 の依存、Apache-2.0 ライセンスを確認した。
  `testImplementation` のみで使い、アプリの実行時依存を増やさない。
- [公式の導入案内](https://kotest.io/docs/proptest/property-based-testing.html)と
  同版の公開 sources JAR の `PropTestConfig`・`Arb` API を確認した。
  設定 API の opt-in は共通設定関数へ限定する。
- 入力・上限・コマンド・レポート・seed の扱いの正本は
  [ビルド・検証の手引き](../../guides/android.md#プロパティベーステスト)に集約する。

## 実行結果

各コマンドはリポジトリルートから、上記 JDK・SDK と Gradle キャッシュを設定して実行した。
ローカル環境の絶対パスや端末情報は公開記録に含めない。

| ID | コマンド・条件 | 結果 |
| --- | --- | --- |
| V1 | `./gradlew --console=plain :app:testDebugUnitTest --tests dev.orgmobile.reader.OrgParserTest --tests dev.orgmobile.reader.DocumentDecoderTest` | 終了0、既存11テスト成功、Gradle 6秒 |
| V2 | `./gradlew --console=plain :app:testDebugUnitTest --tests '*PropertyTest'` | 終了0、6性質×1,000例成功、Gradle 3秒（依存取得済み）。初回コンパイルは設定 API の opt-in 警告で失敗し、明示的 opt-in 後に成功。警告を無効化していない |
| V3a | 見出しの期待レベルだけを一時的に `depth + 1` にし、`./gradlew --console=plain :app:testDebugUnitTest --tests '*OrgParserPropertyTest*heading*' -PpropertyTestSeed=42` | 終了1、最初の反例で失敗。生成深さ58から1、生成文字列から空文字列へ縮小。seed=42、Kotest版・回数・反例をレポートに記録 |
| V3b | 同じ一時変更・同じコマンドに `--rerun-tasks` を追加 | 終了1、元入力・縮小入力・seed が V3a と同一であることを XML の失敗本文で照合。その後一時変更を撤去 |
| V4 | `python3 scripts/run_coverage.py --base-ref main` | 終了0、clean → `check assembleDebug` → カバレッジ生成・判定成功。Gradle 24秒。Debug / Release 各37テスト成功、失敗・エラー・スキップ0、Lint・APK生成成功、行209/214（97.66%）・分岐73/87（83.91%）。本番ソース変更なしのためファイル単位の低下比較は対象外。Lint は新版通知の Hint 7件、警告・エラー0 |
| V5 | `python3 -m unittest discover -s scripts/tests -v`、`git diff --check` | 終了0、Python 33テスト成功、差分の空白エラーなし |

V4 のテスト XML・HTML とカバレッジは手引きに記載した標準出力先で確認した。
V4 のプロパティテスト所要時間（XML のクラス別実行時間の合計）は Debug 0.528秒、
Release 1.102秒だった。キャッシュ・並行実行の条件を含む1回の測定であり、速度の保証や
変更前との性能比較ではない。各性質の seed は以下のとおり。

| 性質 | Debug seed | Release seed |
| --- | --- | --- |
| headings | -7313788148898662493 | 3187427991744270599 |
| lists | 9009792496026217222 | 2054245000912307559 |
| newlines | 3028392938753050014 | -183065166083965790 |
| literal blocks | -7127174096411498750 | -7040666739677436785 |
| independent parses | -5075043902433746828 | -5757812504868340925 |
| UTF-8 | -4436113987628570109 | 5780895780027331400 |

V1 の初回はサンドボックスのネットワークインターフェース制限で Gradle が起動できなかった。
実行環境を許可されたサンドボックス外へ切り替えて実行し、コード起因の失敗と区別した。
V3 はテスト自身の検出確認であり、既存実装の不具合や TDD の Red とは扱わない。
実際の不具合は今回の生成入力では見つかっていない。PIT や検出率の比較測定は未実施。

## CI・端末・残る課題

- 既存の PR / main push CI は `run_coverage.py` → `check` を実行するため、
  追加テストも Debug / Release の必須検証へ含まれる。専用ジョブや探索枠は追加しない。
- 対象コミットの GitHub CI は未確認。今回はコミット・push・PR 作成の依頼がないため行わない。
  最終受け入れ前に、公開対象コミットの `verify` 成功と `android-reports` を確認する。
- 端末確認は対象外。テスト専用の依存・コード・文書のみで、実行時コードと UI を変更しない。
- 1,000例と入力上限は検証の十分性を保証しない。実際の反例や実行負荷が増えた時に保守担当が
  生成器・境界・上限を再検討する。全 Unicode 列、巨大文書、状態遷移全体の網羅は主張しない。
- 統合判断は必須 CI の確認まで保留する。コミット・push・PR 投稿・マージは未実施。

## レビュー記録

作成者：主担当 Codex agent。確認者：別の Codex agent `/root/property_review`。
セルフレビューではない。比較元・対象は上記の未コミット8ファイル。
確認者は差分・状態・履歴・ハッシュ・文書リンク・`git diff --check` を自身で確認し、
Debug / Release テスト XML、カバレッジ JSON、Lint XML と記録を照合した。
Gradle・Python・意図的失敗の実行は主担当の V1〜V5 の結果を参照し、再実行していない。

| ID | 判定 | 根拠・理由 |
| --- | --- | --- |
| R01 | 確認済み | 課題2、6性質×1,000例、seed再現を受け入れ条件と実装で照合 |
| R02 | 確認済み | 空文書・未終了ブロック・不正UTF-8・独立した再解析を含む |
| R03 | 確認済み | Gradle設定と採用版、V4の実行結果を照合 |
| R04 | 確認済み | 未追跡を含む8ファイルに限定。本番コード変更なし |
| R05 | 確認済み | 6.2.6公開sourcesのAPI・設定キー、配布POM、コンパイル成功を照合 |
| R06 | 確認済み | 提供元と版を確認。実測・保証・未実施を文書で区別 |
| R07 | 確認済み | スカラー生成のサロゲート除外、UTF-8拒否6種、文字保持の期待値を確認 |
| R08 | 確認済み | 生成器、仕様からの期待値、seed設定をコードで追跡 |
| R09 | 確認済み | 既存の解析・デコード境界を維持。テスト専用の追加 |
| R10 | 確認済み | Kotestは既定方針に対応。共有生成器と設定以外の抽象化なし |
| R11 | 確認済み | 合成ストリームは `use` で閉じる。解析間の状態独立性を直接検証 |
| R12 | 未確認 | 公開コード・合成入力への限定は確認。利用先の保存・入力利用条件は契約・アカウントの証拠が対象にない。必要時に利用責任者が設定・契約を確認 |
| R13 | 確認済み | 対象差分・記録に秘密・私的文書・URI・ローカル専用資料の混入なし |
| R14 | 確認済み | 新規入力は合成データのみ。権限・実ファイル・外部送信の変更なし |
| R15 | 確認済み | Kotest配布POMで提供元・Apache-2.0を確認。テスト依存のみ |
| R16 | 確認済み | 見出し・リスト・リテラル・独立性は明示的期待値。UTF-8は経路一致に加え本文保持を検証 |
| R17 | 確認済み | JVM層で対象条件を検証。両variant各37件、失敗・スキップ0をXMLで確認 |
| R18 | 確認済み | V3の期待値改変が最初の反例で失敗。seed42と縮小結果を失敗XMLで確認 |
| R19 | 確認済み | V4ログ、カバレッジJSON、テストXML、Python結果を照合。テスト削除・閾値緩和なし |
| R20 | 未確認 | 対象コミットの `verify` 成功・成果物を公開後に確認。端末はテスト専用変更のため対象外 |
| R21 | 確認済み | 日本語・絵文字・広いUnicodeスカラー入力を生成し、制限を明記 |
| R22 | 対象外 | UI・操作・支援技術の変更なし |
| R23 | 確認済み | 実行・再現手順と生成データの用途が実装に一致 |
| R24 | 確認済み | PBT導入に限定。3テストファイルと設定・文書に収まる |
| R25 | 確認済み | 設定→JUnit→check/CI→レポートの接続を照合。文書の改善2件も再確認 |
| R26 | 対象外 | 性能改善の主張なし。実行時間は単回の測定値として明記 |
| R27 | 対象外 | 保存・移行・外部サービス・配布方法の変更なし |
| R28 | 確認済み | Kotest採用、入力上限と検出能力の限界を照合。CI・契約条件の未確認を区別 |
| R29 | 確認済み | 必須指摘なし。改善2件の修正を再確認。保守担当の再検討条件とCI確認条件を記録 |
| R30 | 確認済み | 多様な入力と反例再現で品質を改善。十分性・検出率の過大な保証なし |

### 指摘と残るリスク

- 修正必須の指摘：なし。
- R25改善提案：テストの両variant実行とDebugのみのカバレッジ計測を明確化し、
  開発手順の初期導入手順へ実施済み範囲を補足。別agentが更新差分を再確認し解消。
- R12・R20の未確認は上記理由・次の確認方法のとおり。CIの成功を待つ最終受け入れは、
  公開対象コミットについて保守担当が判断する。
- 判定：**未確認のため保留**。実装の修正必須指摘はなく、必須CI確認を含む統合判断は未完了。

別agentが最終確認した内容の SHA-256 は以下のとおり。本記録自身のハッシュは
レビュー節を追記する直前の版を指す。追記したレビュー節は主担当が返答原文と照合した。

```text
d53b8d6f6414dacf02afe796c2a8e55e36d48f26e0971823991c7f3940181da3 README.md
223e2572b6701e2d6afd2d9008f3efcd25c3e78dfd2712a9b7092760cbaf7cc7 app/build.gradle.kts
9e43da3a537a40642b090ab18efc4522d0e3011da3119e9d5fe3d7bb95e6cc13 docs/guides/android.md
2a6b54b75593d31785d3e28f15629d1f0c710f1bfd0d1993e75eb80388fe449d docs/workflow/development.md
1cf921819085ff62d130f12bbc66652825b0f736a2318522036a504e6a38cd4b app/src/test/java/dev/orgmobile/reader/PropertyInputs.kt
c3d14e8b1648f91a8ba8cd558e0d09b0ab4bdbd23ad982eccfb53aa71f0b5b5c app/src/test/java/dev/orgmobile/reader/OrgParserPropertyTest.kt
3cff365f6b586112dc01859cc4ccf211692c98df8042c80a4058a6bdca5af789 app/src/test/java/dev/orgmobile/reader/DocumentDecoderPropertyTest.kt
9e10baee7505d5d7c871124f9b451cf87a76a394224474ab51fc8eb65fda1c90 docs/records/verification/2026-11-04-property-tests.md
```
