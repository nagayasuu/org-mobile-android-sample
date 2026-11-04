# Android の開発環境とビルド・検証

[開発手順](development-workflow.md)から参照する、環境構築と実行コマンドの手引き。バージョンはリポジトリのビルド設定と CI 定義に合わせて更新する。利用経路の検証は[自動 E2E テスト](#自動-e2e-テスト)に集約する。

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

自動テストでは、日本語の解析・UTF-8 読み込み、不正な文字コード、空ファイル、対応外構文の保持、長い文書、読み込み失敗と再試行、URI からの読み込み、ファイル選択の取り消し、画面再作成後の文書と閲覧位置の保持、更新したファイルの再読み込み、一覧の末尾へのスクロールを確認する。Android の画面・ファイルアクセスのテストには Robolectric の API 35 環境とテスト専用の文書プロバイダーを使う。標準ファイル選択を通す検証は下記の E2E で行い、Dropbox 接続は自動化の未対応範囲として記録する。

## 自動 E2E テスト

[`ReaderE2eTest`](../app/src/androidTest/java/dev/orgmobile/reader/ReaderE2eTest.kt) は、
実際の標準 DocumentsUI で Downloads の文書を選び、アプリの表示を検証する。
選択結果のスタブやテスト専用プロバイダーは使わない。
[UI Automator 2.4.0](https://developer.android.com/jetpack/androidx/releases/test-uiautomator)、
[Espresso 3.7.0 / AndroidX Test 1.7.0 / ext.junit 1.3.0](https://developer.android.com/jetpack/androidx/releases/test)
をテスト APK のみに追加した。新しい製品依存はない。

### 環境と実行

[Gradle Managed Devices](https://developer.android.com/studio/test/managed-devices) を
AGP 9.2.1 の `managedDevices.localDevices` で構成する。
`pixel2Api37` は Pixel 2、API 37、`systemImageSource = "google"`、4 KB ページの通常イメージを使う。
ABI は x86_64 に固定し、`system-images;android-37.0;google_apis;x86_64` を使う。
ATD は標準選択画面を省く可能性があるため採用しない。
初回はネットワーク接続とイメージ用のディスク空き容量が必要。
Linux では `/dev/kvm` の読み書き権限を確認する。
CI は使い捨て runner の KVM デバイスに直接読み書き権限を設定し、エミュレーター起動前に検査する。
SDK と AVD の両方に十分な空き容量を用意する（今回の AVD の userdata は約7.4 GBの空きを要求した）。
起動失敗時は SDK だけでなく AVD の保存先も確認する。
`ANDROID_HOME` は SDK の実体パスを指定する。導入時の AGP 9.2.1 では、
シンボリックリンク経由のパスで Managed Device のイメージ検索に失敗した。

```sh
sdkmanager 'platforms;android-37.0' 'build-tools;37.0.0' emulator 'system-images;android-37.0;google_apis;x86_64'
./gradlew --console=plain :app:pixel2Api37DebugAndroidTest -Pandroid.testoptions.manageddevices.emulator.gpu=swangle
```

JDK 17 と通常のビルド環境を使う。エミュレーターの既定言語は en-US とし、
Downloads のルート名だけ英語に依存する。本文は日本語で検証する。
描画は `swangle`（ANGLE + SwiftShader）を使う。導入環境の Emulator 37.2.13 では
`swiftshader_indirect` が描画スレッドでクラッシュしたため、上の指定をローカルと CI でそろえる。
通常 AOSP revision 6 はシステムサービスの起動に失敗したため、Google APIs 版を選んだ。
個人のファイル・アカウントを含まない専用環境で実行する。
接続済みの実機を対象にする `connectedAndroidTest` はこの手順には使わない。

CI は [Android E2E](../.github/workflows/e2e.yml) の `workflow_dispatch` のみ。
GitHub の Actions から実行対象のブランチを選ぶ。新規ワークフローは既定ブランチに
入った後に手動実行できる。PR の必須 `verify` と通常の `check assembleDebug` は維持する。
週次実行・PR 必須化は、実行時間と安定性を継続確認してから判断する。

### 入力・初期化・合否

各テスト前に、新しい Activity を開き、アプリの永続 URI 読み取り権限を解除する。
アプリ自身が所有する、固定名 `org-reader-e2e-{smoke,long,invalid}.org` の前回分だけを削除し、
MediaStore Downloads に作り直す。広いストレージ権限やシェルでのファイル書き込みは不要。
公開 [`examples/smoke.org`](../examples/smoke.org) はテスト assets からそのままコピーする。
長文は160行のリストと末尾の見出し・本文、不正 UTF-8 は `C3 28` の2バイトを生成する。
正常文書にも不正文書にも `application/octet-stream` を付け、配置後の文書名を検査する。
`text/plain` は MediaStore が `.txt` を追加するため使わない。
アプリは `*/*` で選択し、実際の内容に応じた文字コードの成否を確認する。

| シナリオ | 期待結果 |
| --- | --- |
| 公開サンプルと長文 | 日本語見出し・本文・箇条書き・番号付きリストを表示し、別文書の末尾までスクロールできる |
| 取り消しと回転 | 途中の行番号と先頭行の上端位置を選択取り消し後・横向き回転後に保持し、文書名と末尾を確認できる |
| 不正 UTF-8 からの復帰 | エラー案内が出て、正常文書を再選択すると本文を表示し、エラー案内が消える |

読み込み完了は文書名、エラーは案内文、回転は横向きの構成と閲覧位置を条件で待つ。
Downloads のナビゲーションが閉じてからファイルを押し、選択による画面遷移も待つ。
各条件の上限は15秒。回転の条件は50ms間隔で再確認する。
Espresso でアプリ内の操作・表示を同期し、Managed Devices でアニメーションを無効化する。
タイムアウト・アサーション不一致は失敗とし、失敗を隠す自動リトライは追加しない。
テスト終了時は画面・UI 階層を保存してから Activity を閉じ、権限・作成文書を片付け、回転固定を解除する。
中断時の残存文書も次の開始時にアプリ所有分のみ片付ける。

### 結果と成果物

| 出力 | 場所 |
| --- | --- |
| HTML | `app/build/reports/androidTests/managedDevice/` 以下 |
| XML・実行ログ | `app/build/outputs/androidTest-results/managedDevice/` 以下 |
| 各テスト終了時の PNG・UI 階層 XML | `app/build/outputs/managed_device_android_test_additional_output/` 以下 |
| テスト APK | `app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk` |

runner の `additionalTestOutputDir` に診断を保存し、未指定の場合のみ端末上の
アプリ専用 external files の `e2e/` を使う。診断の保存失敗は warning を出し、
シナリオの成否と区別する。失敗段階はアサーションの文言と `ReaderE2E` のログで追う。
CI は `android-e2e-reports` に上記結果・コミット SHA・APK SHA-256、
`org-reader-e2e-apks` に本体とテスト APK を保存する。環境作成の失敗も Gradle ログで確認する。
収集先は明示したビルド出力だけであり、端末全体のデータを収集しない。

導入時のコマンド・結果・未確認は[検証記録](verification/2026-11-05-e2e-tests.md)を参照する。
E2E の成功は Dropbox の保存・クラウド接続、Pixel 10a の実機、TalkBack、大容量の性能を保証しない。
利用経路の検証は E2E で行う。未対応の条件と追加方針は[開発手順](development-workflow.md#e2e-gaps)に集約する。既存の JVM・Robolectric・Lint は共通検証として維持する。

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

## ミューテーションテスト

[PIT 1.30.1](https://github.com/hcoles/pitest/releases/tag/1.30.1)（Apache-2.0）の
CLI を専用の `JavaExec` タスクで起動する。Android 用プラグイン
`pl.droidsonroids.pitest` 0.2.27 は AGP 9 の `applicationVariants` 削除により
構成に失敗するため採用しない。JDK 17、Gradle 9.4.1、AGP 9.2.1、
内蔵 Kotlin 2.2.10、JUnit 4.13.2、Kotest 6.2.6 で試験した。

```sh
# 具体例とプロパティテストを使う通常の手動実行
./gradlew --console=plain -I gradle/mutation.init.gradle :app:pitestDebug

# 比較用：現在の具体例テストだけを使う
./gradlew --console=plain -I gradle/mutation.init.gradle :app:pitestDebugExamples
```

設定は [`mutation.gradle`](../gradle/mutation.gradle)、明示的に読み込む入口は
[`mutation.init.gradle`](../gradle/mutation.init.gradle) に集約する。
初回は Maven Central への接続が必要。通常の `check assembleDebug`・カバレッジ・
既存 CI には追加しない。初期化スクリプトを指定しない限り PIT の構成も取得も行わない。
タスクは毎回実行し、各モードの古いレポートを消してから生成する。

| 条件 | 固定値・範囲 |
| --- | --- |
| 変更対象 | `OrgParser` と `$` で始まる内部クラス、`DocumentDecoder` |
| テスト | `OrgParserTest`・`DocumentDecoderTest`、通常は対応する2つの `PropertyTest` も含む |
| 変更演算子 | PIT 1.30.1 の `DEFAULTS`。追加の除外なし |
| プロパティ入力 | 上節と同じ6性質・各1,000例・サイズ上限。seed は各性質42に固定 |
| プロセス | 1 thread、timeout は通常実行時間の4倍 + 10,000ms |
| 合否 | mutation score 100%以上、XML の全件が `KILLED`、両クラスの mutation が存在すること |

`propertyTestSeed` は通常のテスト用の指定であり、PIT 内の seed は常に42である。
履歴による間引きは使わず、失敗 seed の自動保存も無効にする。
`OrgBlock` などのデータ保持、Android の生成クラス、テスト、依存ライブラリ、
Robolectric を使う UI・ファイルアクセスのテストは変更対象へ広げない。
通常の Debug テストタスクが公開するクラスパスとテスト出力を再利用し、AGP が
本番クラスを JAR にまとめるため `mutableCodePaths` を明示する。
対象クラスは上記の名前で限定する。AGP の出力パスはハードコードしない。

| 出力 | 場所 |
| --- | --- |
| 通常の HTML / XML | `app/build/reports/pitest/combined/index.html` / `mutations.xml` |
| 具体例のみの HTML / XML | `app/build/reports/pitest/examples/index.html` / `mutations.xml` |

PIT は変更前のテストが成功することも確認する。生き残り・未実行・実行エラー・
タイムアウトはレポートで区別する。PIT の score は検出扱いの一部エラーも含み得るため、
XML の `KILLED` 以外を追加検査で拒否する。両クラスの計測欠落・空レポートも失敗とする。
試験後の31件全検出を維持するため最低スコアは100%とした。新しい生き残りは仕様と
照合し、意味のあるテスト不足を直す。条件変更時の閾値の再判断は
[開発手順](development-workflow.md#mutation-score-の閾値を決める手順)に従う。

JaCoCo の引数を引き継がず別 JVM で実行し、通常のテスト結果・カバレッジへ混ぜない。
PIT もその依存も APK へ含めない。Kotlin 用 Arcmutate プラグイン未導入の案内が出るが、
今回の試験には導入せず、生成コードのノイズはソースと照合した。
既定演算子は正規表現の書き換えや fluent API の引数変更を網羅しないため、
見出しレベル固定・末尾欠落・不正 UTF-8 受け入れの一時的な誤実装でも検出を確認した。
比較結果・検出した不足・CI を追加しない理由は
[検証記録](verification/2026-11-04-mutation-tests.md)を参照する。

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
