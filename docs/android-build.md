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

## CI

[`.github/workflows/android.yml`](../.github/workflows/android.yml) は PR と `main` への push で、同じ `check assembleDebug` を実行する。APK は `org-reader-debug`、検証レポートは `android-reports` という名前の成果物として取得する。アップロード対象は明示した APK と `app/build/reports/` のみとする。

GitHub 上での実行結果は、push または PR 作成後に別途確認する。ワークフローの追加やローカル検証の成功だけで CI が成功したとはみなさない。

確認時は対象コミット、run の URL と結果を記録し、同じ run の `android-reports` と `org-reader-debug` を使う。文書だけの変更でも、実行された CI の結果は実際に確認するまで未確認とする。PR 作成や結果・成果物の取得には GitHub の画面、API、利用可能な連携ツールを使え、`gh` は前提にしない。

CI 定義を変更した場合は、利用できれば actionlint で静的確認し、GitHub 上の実行結果も確認する。actionlint の成功は、SDK の導入や Gradle タスクの成功を代替しない。
