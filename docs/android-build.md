# Android の開発環境とビルド・検証

[開発手順](development-workflow.md)から参照する、環境構築と実行コマンドの手引き。バージョンはリポジトリのビルド設定と CI 定義に合わせて更新する。端末での操作は[端末確認手順](device-testing.md)を参照する。

## 開発環境

| 項目 | 使用するバージョン |
| --- | --- |
| JDK | 17（`java` と `javac` を含む。ローカル検証は Temurin 17.0.21） |
| Gradle | 9.4.1（同梱の Wrapper を使う） |
| Android Gradle Plugin | 9.2.1 |
| Kotlin | AGP の内蔵 Kotlin を使う |
| Android SDK | Platform 37.0、Build Tools 37.0.0、Platform Tools |
| Android API 設定 | minSdk 26、compileSdk / targetSdk 37 |

[AGP の互換性表](https://developer.android.com/build/releases/agp-9-2-0-release-notes)に合う組み合わせを固定し、Android 17（API 37）を対象にする。[AGP の内蔵 Kotlin](https://developer.android.com/build/migrate-to-built-in-kotlin)を使うため、`org.jetbrains.kotlin.android` プラグインは追加しない。

1. JDK 17 をインストールし、`JAVA_HOME` を JDK のディレクトリに設定する。`java -version` と `javac -version` を確認する。
2. [Android Studio または Command-line Tools](https://developer.android.com/studio)で SDK を用意し、`ANDROID_HOME` を SDK のディレクトリに設定する。Command-line Tools の `bin` と SDK の `platform-tools` を `PATH` に追加する。JDK 17 と組み合わせて検証した CLI は Command-line Tools 19.0（Linux 用の [公式配布 ZIP](https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip)）であり、CI でもこの版を指定している。CLI で同じ環境を用意する場合は、この ZIP の `cmdline-tools` を SDK 内の `cmdline-tools/19.0` へ展開し、その `bin` を `PATH` に追加する。
3. 次のコマンドでライセンスを確認・受諾し、必要なパッケージを入れる。

```sh
sdkmanager --licenses
sdkmanager 'platforms;android-37.0' 'build-tools;37.0.0' 'platform-tools'
```

SDK の場所は、`ANDROID_HOME` の代わりに `local.properties` の `sdk.dir` でも指定できる。環境固有のパス、SDK、JDK、キャッシュ、署名鍵はコミットしない。初回のビルドと Robolectric の初回テスト実行には、公式配布元・Google Maven・Maven Central などへのネットワーク接続が必要になる。

## 共通のビルド・検証コマンド

リポジトリのルートで実行する。

```sh
./gradlew --console=plain check assembleDebug
```

このコマンドで Debug / Release の JVM テスト、Android Lint、Debug APK の生成を行う。必要な検証を個別に実行する場合は次を使う。

AGP 9 の既定で Release テストが省略されないよう、`app/build.gradle.kts` の `beforeVariants` で両ビルド種別のホストテストを明示的に有効にしている。

```sh
./gradlew :app:testDebugUnitTest
./gradlew :app:testReleaseUnitTest
./gradlew :app:lintDebug
./gradlew :app:assembleDebug
```

実装中に関連テストだけを実行する例：

```sh
./gradlew :app:testDebugUnitTest --tests 'dev.orgmobile.reader.OrgParserTest'
```

個別実行は早いフィードバックを得るために使う。アプリ・テスト・ビルド設定の変更では、完了前に共通の `check assembleDebug` も実行する。

| 出力 | 場所 |
| --- | --- |
| Debug APK | `app/build/outputs/apk/debug/app-debug.apk` |
| Debug テストの HTML レポート | `app/build/reports/tests/testDebugUnitTest/index.html` |
| Release テストの HTML レポート | `app/build/reports/tests/testReleaseUnitTest/index.html` |
| Lint レポート | `app/build/reports/lint-results-debug.html` |

Kotlin の警告と Lint の警告はビルドを失敗させる。例外として、`app/lint.xml` では依存関係・Gradle の新版通知（`GradleDependency`、`NewerVersionAvailable`、`AndroidGradlePluginVersion`）を情報レベルにする。検証済みの組み合わせを固定し、更新を一つの変更として再検証するためであり、通知自体はレポートに残す。互換性やコードの問題の検出は有効なままとする。

自動テストでは、日本語の解析・UTF-8 読み込み、不正な文字コード、空ファイル、対応外構文の保持、長い文書、読み込み失敗と再試行、URI からの読み込み、ファイル選択の取り消し、画面再作成後の文書と閲覧位置の保持、更新したファイルの再読み込み、一覧の末尾へのスクロールを確認する。Android の画面・ファイルアクセスのテストには Robolectric の API 35 環境とテスト専用の文書プロバイダーを使う。これは実機のファイル選択画面や Dropbox の接続確認を代替しない。

## プロパティベーステスト

[`Kotest Property 6.2.6`](https://github.com/kotest/kotest/releases/tag/v6.2.6) を
テスト依存として使い、JUnit 4 の `@Test` 内から `runTest` と `checkAll` を呼ぶ。
専用 runner・プラグイン・探索用 CI は追加しない。JDK 17、AGP 9.2.1 の内蔵
Kotlin 2.2.10、Gradle 9.4.1、coroutines-test 1.10.2 と組み合わせている。
Kotest の推移依存はテストの構成だけに入り、APK へは含まれない。
`PropTestConfig` の採用版 API には、設定関数だけで `ExperimentalKotest` を opt-in する。

[`OrgParserPropertyTest`](../app/src/test/java/dev/orgmobile/reader/OrgParserPropertyTest.kt) と
[`DocumentDecoderPropertyTest`](../app/src/test/java/dev/orgmobile/reader/DocumentDecoderPropertyTest.kt) で
次の6つの性質をそれぞれ1,000例検証する。1件でも反例があれば失敗する。

| 性質 | 入力と上限 |
| --- | --- |
| 見出しの深さ・タイトル保持 | 深さ1〜64、改行なしの合成タイトル |
| リストの種別・本文・字下げ保持 | `-`・`+`・字下げ付き `*`・`0`〜`9999` の番号、空白/タブ0〜16個、区切り3種 |
| LF / CRLF・先頭 BOM の同値性 | 空・見出し・リスト・対応外構文・リテラルを0〜24断片組み合わせた文書 |
| リテラルの保持と終了後の通常解析 | 大小文字のブロック名、構文風の行・空行・異なる終了名 |
| 解析の独立性 | 空・本文・未終了ブロックを含む A → B → A、仕様から作った期待値 |
| UTF-8 の内容保持と不正入力拒否 | 直接解析との一致に加え、固定接頭辞付き本文の完全保持、不正6種を合成本文の後へ挿入 |

共通生成器 [`PropertyInputs`](../app/src/test/java/dev/orgmobile/reader/PropertyInputs.kt) は
1行あたり0〜64個の Unicode スカラー値（最大128 UTF-16単位）を生成する。
日本語・絵文字・空白・タブ・NUL・記号も選択肢に含む。
孤立サロゲート、改行文字（CR/LF/NEL/LS/PS）、BOM は行から除き、改行と先頭 BOM は
文書の組み立てで追加する。文書は最大72行、約4千 UTF-16単位であり、大容量文書の性能検証とは区別する。
不正入力は孤立継続バイト・過長表現・不正継続・途切れ・サロゲート・Unicode 上限超過を扱う。
私的な文書・URI は使わない。

```sh
# 開発中に対象の性質を各1,000例実行（毎回実行する場合は --rerun-tasks）
./gradlew :app:testDebugUnitTest --tests '*PropertyTest'

# 失敗したクラス/メソッドに絞り、記録された seed を再現
./gradlew :app:testDebugUnitTest --tests '*OrgParserPropertyTest*' -PpropertyTestSeed=42 --rerun-tasks
```

通常は性質ごとに新しい seed を選び、性質名・Kotest 版・回数・seed を標準出力へ記録する。
再現用の `propertyTestSeed` は Gradle からテスト JVM へ渡す。seed の変更はテストタスクの
入力変更として扱われる。`--tests` で失敗したメソッドまで指定すると当該の探索を再現できる。
[Kotest の shrinking](https://kotest.io/docs/proptest/property-test-shrinking.html) で縮小した反例と
[seed](https://kotest.io/docs/proptest/property-test-seeds.html) は失敗の詳細に残る。
ホームディレクトリの過去の失敗 seed に依存しないよう、自動 seed ファイル保存は無効にする。
発見した実際の不具合は、縮小後の入力を具体例の回帰テストへ追加して修正する。

共通の `check assembleDebug`、カバレッジ計測コマンド、既存 CI の `verify` は、いずれも
テストを Debug / Release の両方で実行する。カバレッジの計測対象は Debug のみである。
HTML レポートは共通のテスト出力先にあり、性質ごとの実行時間と標準出力
（成功時の seed も含む）を確認できる。XML は `app/build/test-results/testDebugUnitTest/` と
`testReleaseUnitTest/` に出る。CI の `android-reports` には HTML が保存される。
導入時の実測と意図的な反例による失敗・再現確認は[検証記録](verification/2026-11-04-property-tests.md)を参照する。
1,000例や入力上限は十分性の保証ではなく、不具合や実行負荷に応じて見直す。

## 依存構造の検査

[`ArchitectureTest`](../app/src/test/java/dev/orgmobile/reader/ArchitectureTest.kt) は
[ArchUnit 1.5.1](https://github.com/TNG/ArchUnit/releases/tag/v1.5.1) の
コアライブラリを通常の JUnit 4 `@Test` から呼び出す。専用 runner や Gradle
プラグインは追加せず、テスト用の依存だけを追加するため APK には含まれない。
JDK 17、Gradle 9.4.1、AGP 9.2.1 での確認結果は
[検証記録](verification/2026-11-03-architecture-checks.md)を参照する。

検査は `ClassFileImporter.importPackages("dev.orgmobile.reader")` で本番の
コンパイル済みクラスを読み込む。AGP が渡すアプリの JAR も含め、テストクラスの
実際の出力場所だけを除外する。ソースの import 一覧は検査しない。
クラス名の完全一致と `$` で始まる内部・匿名・Kotlin 生成クラスを同じ責務として
扱い、広い内部クラス除外は設けない。各規則は対象が空なら失敗し、別のテストでも
全ルートと既知の内部クラスの存在、テストクラスの除外を確認する。

| 対象 | 禁止する依存 |
| --- | --- |
| `OrgParser` / `OrgBlock` のクラス群 | `android` / `androidx` / `com.android` 配下、両クラス群以外のアプリクラス、`java.io` / `java.nio.file` / `java.net` 配下 |
| `DocumentDecoder` のクラス群 | Android 関連の上記3パッケージ、`DocumentDecoder` / `OrgParser` / `OrgBlock` 以外のアプリクラス。JDK のストリーム・文字コード処理は許可 |
| `ReaderViewModel` のクラス群 | `MainActivity` / `OrgAdapter` / `ContentDocumentSource` のクラス群と、`android.app` / `android.view` / `android.widget` / `android.webkit` / `androidx.activity` / `androidx.fragment` / `androidx.recyclerview` 配下。`DocumentSource`、URI、ViewModel・状態保存は許可 |

違反はクラス間の型参照・メソッド呼び出しなどの直接依存で判定する。リフレクションで
文字列から読み込むクラスや、実行時の遅延・資源解放は保証しない。新しい画面や
ファイルアクセス実装、パッケージの追加時は、責務に合わせて規則も見直す。

```sh
./gradlew :app:testDebugUnitTest --tests 'dev.orgmobile.reader.ArchitectureTest'
./gradlew :app:testReleaseUnitTest --tests 'dev.orgmobile.reader.ArchitectureTest'
```

通常の `check assembleDebug` と既存 CI の `verify` にも含まれる。レポートは
上記 Debug / Release の JVM テスト HTML と
`app/build/test-results/testDebugUnitTest/` / `testReleaseUnitTest/` の XML に出力する。
CI では HTML を `android-reports` に保存する。
導入時の意図的な違反・対象欠落の検出結果、一時変更の撤去と正常復帰は
[検証記録](verification/2026-11-03-architecture-checks.md)へ残す。

## カバレッジ計測

[AGP 標準の JaCoCo 連携](https://developer.android.com/studio/test/coverage-report)を使い、
Debug の JVM テスト全体を計測する。計測条件は
[`gradle/coverage.gradle`](../gradle/coverage.gradle)へ集約している。
[JaCoCo 0.8.14](https://www.jacoco.org/jacoco/trunk/doc/changes.html)を固定し、
AGP 9.2.1・Gradle 9.4.1・内蔵 Kotlin・Robolectric 4.16・JDK 17 で検証した。
Kotlin の生成処理は JaCoCo の標準フィルターを使い、アプリの内部クラスは除外しない。
Robolectric 用に `includeNoLocationClasses` を有効にし、エージェントの対象を
`dev.orgmobile.reader.*` に限定する。名前空間やソース配置を変える際は設定と検査を見直す。

```sh
# clean → check assembleDebug → Debug 全テストのレポート → 80%・低下判定
python3 scripts/run_coverage.py --base-ref main

# 比較元がない初回の実行（80%判定は有効、低下判定は未実施と表示）
python3 scripts/run_coverage.py

# レポートだけを調べる場合。部分実行後の結果は受け入れ判定に使わない
./gradlew :app:createDebugUnitTestCoverageReport
python3 scripts/check_coverage.py
```

`run_coverage.py` は毎回 clean で古い実行データ・レポートを消し、共通検証と
レポート生成を同じ Gradle 呼び出しで行う。Debug テストを二重には実行しない。
Release テスト・Lint・APK 生成も維持する。計測はテスト JVM のみに作用し、
APK に計測エージェントを追加しない。

| 出力 | 場所 |
| --- | --- |
| HTML | `app/build/reports/coverage/test/debug/index.html` |
| XML | `app/build/reports/coverage/test/debug/report.xml` |
| 実行データ | `app/build/outputs/unit_test_code_coverage/debugUnitTest/testDebugUnitTest.exec` |
| 比較元の HTML／XML（比較対象がある場合） | `app/build/reports/coverage/baseline/` |
| 比較元・対象 SHA、対象ファイル、判定 | `app/build/reports/coverage/comparison.json` |

AGP のレポートはアプリのコンパイル済みクラスを対象とし、テスト、依存 JAR、
Android の生成 `R`／`BuildConfig` を集計しない。アプリ実装を率のために除外する設定は
追加していない。インライン由来の依存ソース名が XML に出る場合があるが、カウンターの
ないものに限って許容する。検査は `app/src/main/java` の `.kt`／`.java` がすべて XML に
存在し、全体とソース群のカウンターが一致することも確認する。XML・実行セッション・
ソース・行の実行データの欠落や不整合は失敗させる。

全体の行・分岐をそれぞれ丸め前の値で80%以上と判定する。低下判定は変更した既存
ソースファイル群の合計について行・分岐を比較する。新規ファイルは全体の判定に含む。
削除・改名は比較可能な既存ファイル群から外し、変更対象がなければその旨を表示する。
分岐の分母が0ならその指標は対象外と明示する。比較元が指定されているのに取得・計測・
解析に失敗した場合は、未実施として合格させず失敗する。

CI の PR ではマージ先ブランチを fetch した最新 SHA、`main` push ではイベントの
`before` SHA を使う。比較対象があれば `git archive` で公開ファイルだけを一時ディレクトリへ
展開し、変更側と同じ `coverage.gradle` を適用して基準側の全 Debug テストを実行する。
AGP・Gradle・依存・テスト設定などのビルド入力が異なる場合は比較を止め、同じ条件に
そろえた検証を求める。テストケース自体は各版のものを使う。
基準側の APK やローカル設定はコピーしない。比較で SDK を利用するため
`ANDROID_HOME` を指定する（`local.properties` だけの設定では不足する）。

判定スクリプトの回帰テストは `python3 -m unittest discover -s scripts/tests -v` で実行する。
80%境界、行・分岐の低下、0分母、欠落・破損 XML の拒否を確認する。
実測・未確認事項は[検証記録](verification/2026-11-03-coverage.md)を参照する。

## CI

[`.github/workflows/android.yml`](../.github/workflows/android.yml) は PR と `main` への push で、`scripts/run_coverage.py --github-event` で共通検証とカバレッジの80%・低下判定を実行する。PR は作成・コミット更新・再オープンに加え、タイトルや説明の編集でも実行する。必須ジョブ `verify` は先に Python 3 で Git フック・メッセージ検証のテストと、コミットメッセージ・PR タイトルの検証を行う。対象範囲・ローカル実行・フックの導入は[Git 運用規約](git-workflow.md#自動検証と-git-フック)に従う。2026-11-02 に正常系、不正コミット・タイトルの拒否、タイトル修正後の再実行と正常復帰を確認した。対象コミットと run は[検証記録](verification/2026-11-02-git-hooks.md)を参照する。

APK は `org-reader-debug`、検証レポートは `android-reports` という名前の成果物として取得する。アップロード対象は明示した APK と `app/build/reports/` のみとする。

GitHub 上での実行結果は、push または PR 作成後に別途確認する。ワークフローの追加やローカル検証の成功だけで CI が成功したとはみなさない。

確認時は対象コミット、run の URL と結果を記録し、同じ run の `android-reports` と `org-reader-debug` を使う。文書だけの変更でも、実行された CI の結果は実際に確認するまで未確認とする。PR 作成や結果・成果物の取得には GitHub の画面、API、利用可能な連携ツールを使え、`gh` は前提にしない。

CI 定義を変更した場合は、利用できれば actionlint で静的確認し、GitHub 上の実行結果も確認する。actionlint の成功は、SDK の導入や Gradle タスクの成功を代替しない。
