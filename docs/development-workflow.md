# 開発手順

このリポジトリでは、最小の機能を一本通し、ビルド、テスト、CI、端末での動作確認を早期に整える。人と agent は同じ検証手順を使い、実行結果に基づいて変更を評価する。GitHub CLI（`gh`）は必須にしない。

## 文書の役割

| 文書 | 記載する内容 |
| --- | --- |
| [AGENTS.md](../AGENTS.md) | agent が作業開始時に読む指示と、適用する手順書への参照 |
| 本書 | 実装から検証・動作確認までの順序、実行方法、完了条件 |
| [Git 運用規約](git-workflow.md) | ブランチ、コミット、PR、レビュー、統合、履歴操作のルール |

実行コマンドと検証手順は本書に集約し、Git 運用規約から参照する。

## 1. 最初の機能と受け入れ条件を決める

### 最初の機能：既存の org ファイルを閲覧する

Linux PC の Emacs で利用している org ファイルを、Android でもシンプルな UI で読めるようにする。最初の版は閲覧専用とし、次の操作を端から端まで通す。

1. Dropbox アプリから UTF-8 の `.org` ファイルを端末へ手動で保存する。
2. 本アプリの「ファイルを開く」から Android 標準のファイル選択画面を開く。
3. 保存したファイルを選ぶと、見出し・本文・箇条書きが読みやすく表示される。
4. 文書全体を縦にスクロールし、末尾まで読める。

受け入れ条件は、ファイル選択から表示まで完了すること、日本語が文字化けしないこと、見出し・本文・箇条書きを区別できること、長い文書の末尾まで閲覧できることとする。ファイルの選択を取り消すと現在の表示を維持し、読み込みに失敗すると再選択できるメッセージを表示する。

処理は「ファイル選択 → 読み込み → org 解析 → 表示」に分け、解析は画面や Android のファイルアクセスから独立させて自動テストする。見出しの折りたたみ、編集、新規メモの保存、Dropbox との自動同期は後続の機能とする。端末に保存したコピーは、PC 側の更新後に再度保存する。

表示対象は `*` から始まる見出し、通常の本文、`-`・`+`・インデントした `*` の箇条書き、`1.`・`1)` 形式の番号付きリストとする。対応外の構文はテキストとして残す。完全な org-mode のレンダリングを目標にしない。

手動の動作確認対象は Pixel 10a／Android 17 とし、開発用 PC に USB 接続して確認する。テストに利用するファイルは公開可能なサンプルを使い、個人のメモをリポジトリや検証レポートへ含めない。

## 2. コマンドで動く最小アプリを用意する

1. Android の最小アプリと Gradle Wrapper を用意する。
2. 必要な JDK・Android SDK・ビルド設定をそろえ、利用するバージョンと準備方法を記録する。
3. IDE の手操作に依存せず、コマンドでビルドできることを確認する。
4. 最初の自動テストと静的解析を追加し、コマンドから実行できるようにする。
5. 検証用 APK を端末またはエミュレーターへインストールし、起動を確認する。

本番配信の仕組みは必要性に合わせて追加する。初期段階では、検証用 APK を作成して動作確認できる経路を整える。

## 3. 小さな機能をテストとともに実装する

1. 受け入れ条件を確認するテストを用意する。既存動作を変更する場合は、現在の振る舞いも確認する。
2. テストを実行し、期待する理由で失敗していることを確認する。
3. 成功に必要な小さな変更を実装する。
4. ビルド、静的解析、関連テストを実行する。
5. 成功を維持しながら構造を整理し、受け入れ条件を満たすまで繰り返す。

境界で振る舞いを確認し、細かな条件は必要に応じて内部のテストで確認する。テストは準備・実行・検証（Arrange-Act-Assert）が読み取れる形にする。

保存先などをフェイクに置き換えて、高速に実行できるテストを用意する。実際の保存先との接続は別に確認する。静的解析の警告を抑制する必要がある場合は、対象と理由を記録する。

## 4. 同じ検証を CI で実行する

- GitHub Actions に、PR と `main` への push を契機に検証するワークフローを用意する。
- ローカルと CI で共通の Gradle タスクやスクリプトを使い、ビルド、静的解析、テストを実行する。
- 確認用 APK と必要な検証レポートを成果物として保存する。
- 失敗時は、実行ログと対象の変更を確認して修正する。失敗を隠すために検証を無効化しない。
- PR 作成や結果の確認には GitHub の画面、API、利用可能な連携ツールを使える。`gh` のインストールを前提にしない。

## 5. 端末で実際の接続と動作を確認する

- CI で作成した APK を取得し、Android 端末またはエミュレーターへインストールする。
- 実際の保存先を使い、受け入れ条件に沿って入力、保存、表示などを確認する。永続化が対象なら、アプリ再起動後の保持も確認する。
- 使用した成果物、確認環境、操作、期待結果、実際の結果を記録する。
- 初期段階は手動のスモークテストから始め、繰り返しの負担や不具合のリスクに応じて自動化する。

## agent が作業するとき

作業開始時に目的、受け入れ条件、変更範囲、利用可能な検証方法を確認する。各段階で上記のコマンドや確認手順を使い、結果に基づいて実装を進める。

完了報告には、変更点、実行した検証コマンドと結果、CI の確認結果、端末での確認結果、未確認事項を記載する。自動テストの成功と、端末での動作確認はそれぞれの結果を示す。実行環境がない検証は未実行として記録し、利用できる検証を進める。

コミット、push、PR 作成、マージの実行範囲と手順は [Git 運用規約](git-workflow.md) に従う。

## 現在の整備状況と実行コマンド

### 開発環境

| 項目 | 使用するバージョン |
| --- | --- |
| JDK | 17（`java` と `javac` を含む。ローカル検証は Temurin 17.0.21） |
| Gradle | 8.13（同梱の Wrapper を使う） |
| Android Gradle Plugin | 8.13.2 |
| Kotlin | 2.2.21 |
| Android SDK | Platform 36、Build Tools 35.0.0、Platform Tools |
| Android API 設定 | minSdk 26、compileSdk / targetSdk 36 |

[AGP の互換性表](https://developer.android.com/build/releases/agp-8-13-0-release-notes)に合う組み合わせを固定する。Android 17 の新規 API は使用しておらず、Android 17 端末での動作は実機で別途確認する。

1. JDK 17 をインストールし、`JAVA_HOME` を JDK のディレクトリに設定する。`java -version` と `javac -version` を確認する。
2. [Android Studio または Command-line Tools](https://developer.android.com/studio)で SDK を用意し、`ANDROID_HOME` を SDK のディレクトリに設定する。Command-line Tools の `bin` と SDK の `platform-tools` を `PATH` に追加する。JDK 17 と組み合わせて検証した CLI は Command-line Tools 19.0（Linux 用の [公式配布 ZIP](https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip)）であり、CI でもこの版を指定している。CLI で同じ環境を用意する場合は、この ZIP の `cmdline-tools` を SDK 内の `cmdline-tools/19.0` へ展開し、その `bin` を `PATH` に追加する。
3. 次のコマンドでライセンスを確認・受諾し、必要なパッケージを入れる。

```sh
sdkmanager --licenses
sdkmanager 'platforms;android-36' 'build-tools;35.0.0' 'platform-tools'
```

SDK の場所は、`ANDROID_HOME` の代わりに `local.properties` の `sdk.dir` でも指定できる。環境固有のパス、SDK、JDK、キャッシュ、署名鍵はコミットしない。初回のビルドと Robolectric の初回テスト実行には、公式配布元・Google Maven・Maven Central などへのネットワーク接続が必要になる。

### 共通のビルド・検証コマンド

リポジトリのルートで実行する。

```sh
./gradlew --console=plain check assembleDebug
```

このコマンドで Debug / Release の JVM テスト、Android Lint、Debug APK の生成を行う。必要な検証を個別に実行する場合は次を使う。

```sh
./gradlew :app:testDebugUnitTest
./gradlew :app:lintDebug
./gradlew :app:assembleDebug
```

| 出力 | 場所 |
| --- | --- |
| Debug APK | `app/build/outputs/apk/debug/app-debug.apk` |
| Debug テストの HTML レポート | `app/build/reports/tests/testDebugUnitTest/index.html` |
| Release テストの HTML レポート | `app/build/reports/tests/testReleaseUnitTest/index.html` |
| Lint レポート | `app/build/reports/lint-results-debug.html` |

Kotlin の警告と Lint の警告はビルドを失敗させる。例外として、`app/lint.xml` では依存関係・Gradle の新版通知（`GradleDependency`、`NewerVersionAvailable`、`AndroidGradlePluginVersion`）を情報レベルにする。検証済みの組み合わせを固定し、更新を一つの変更として再検証するためであり、通知自体はレポートに残す。互換性やコードの問題の検出は有効なままとする。

自動テストでは、日本語の解析・UTF-8 読み込み、不正な文字コード、空ファイル、対応外構文の保持、長い文書、読み込み失敗と再試行、URI からの読み込み、ファイル選択の取り消し、画面再作成後の文書と閲覧位置の保持、更新したファイルの再読み込み、一覧の末尾へのスクロールを確認する。Android の画面・ファイルアクセスのテストには Robolectric の API 35 環境とテスト専用の文書プロバイダーを使う。これは実機のファイル選択画面や Dropbox の接続確認を代替しない。

### CI

[`.github/workflows/android.yml`](../.github/workflows/android.yml) は PR と `main` への push で、同じ `check assembleDebug` を実行する。APK は `org-reader-debug`、検証レポートは `android-reports` という名前の成果物として取得する。アップロード対象は明示した APK と `app/build/reports/` のみとする。

GitHub 上での実行結果は、push または PR 作成後に別途確認する。ワークフローの追加やローカル検証の成功だけで CI が成功したとはみなさない。

### USB 接続した端末でのスモークテスト

1. Pixel 10a／Android 17 の開発者向けオプションで USB デバッグを有効にし、開発用 PC に接続する。端末に表示される接続許可を確認する。
2. 接続状態を確認する。複数台ある場合は、以降の `adb` コマンドで `-s` を使い対象を明示する。`unauthorized` の場合は端末側で許可する。

```sh
adb devices
```

3. GitHub Actions の `org-reader-debug` 成果物から取得した `app-debug.apk` をインストールする。CI の成果物がまだない場合は、ローカルビルドした APK を次のように使い、確認記録で区別する。

```sh
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n dev.orgmobile.reader/.MainActivity
```

4. Dropbox に公開可能なサンプル [`examples/smoke.org`](../examples/smoke.org) を置き、Dropbox アプリから端末のダウンロードフォルダに保存する。
5. 本アプリで「ファイルを開く」を押し、標準の選択画面で保存したファイルを選ぶ。日本語、見出し、本文、箇条書き、番号付きリスト、末尾の本文を確認する。
6. もう一度選択画面を開いて取り消し、現在の文書が残ることを確認する。画面を回転して表示が維持されることも確認する。
7. 空ファイルでは空であることが表示され、不正な UTF-8 のファイルでは再選択を案内することを確認する。
8. 長いサンプルを端末へ転送し、手動スクロールで末尾の `項目 10000` が読めることを確認する。

```sh
python3 - <<'PY'
from pathlib import Path
Path('/tmp/org-reader-long.org').write_text(
    '* 長い文書\n' + '\n'.join(f'- 項目 {i}' for i in range(1, 10001)),
    encoding='utf-8',
)
PY
adb push /tmp/org-reader-long.org /sdcard/Download/org-reader-long.org
```

Dropbox の経路とは別に表示だけを確認する場合は、`adb push examples/smoke.org /sdcard/Download/org-reader-smoke.org` で転送できる。Dropbox からの保存を省略した場合は、その経路は未確認として記録する。

ADB で転送したファイルが標準選択画面に出ない場合は、転送したファイルを次のようにスキャンし、選択画面のフォルダを開き直す。実機確認ではこの操作後にサンプルを選択できた。

```sh
adb shell content call --uri content://media --method scan_file --arg /sdcard/Download/org-reader-long.org
```

確認記録には、日付、APK の取得元と SHA-256、端末と OS、操作、期待結果、実際の結果を残す。ファイルの内容や端末の識別子など、ローカル専用の情報は公開レポートへ含めない。

### 初回実装の検証記録（2026-11-01）

- 解析処理を未実装とした状態で、関連する 7 件のテストが期待値との不一致により失敗することを確認した。
- `./gradlew clean check assembleDebug --console=plain`：成功。Debug / Release 各 16 件のテストが成功し、失敗・スキップは 0 件。Lint はエラー・警告 0 件、新版通知の情報 7 件。
- 実機で、端末のダークモード時に明るい閲覧背景とステータスバーの文字色が合わない問題を発見した。先に回帰テストの失敗を確認し、閲覧画面の明るいテーマに合うシステムバーの表示へ修正した。
- 修正後の `./gradlew check assembleDebug --console=plain`：成功。Debug / Release 各 17 件のテストが成功し、失敗・スキップは 0 件。Lint のエラー・警告は 0 件。
- CI 定義の静的確認：actionlint 1.7.7 で成功。生成 APK の署名検証（`apksigner verify`）、文書のローカルリンク、`git diff --check` も成功。
- GitHub 上の CI：未実行。リモートへの push / PR 作成は行っていない。

#### 実機確認

- 環境：Pixel 10a／Android 17（API 37）、USB 接続。ローカルビルドした Debug APK を `adb install -r` でインストールし、`adb shell am start -W -n dev.orgmobile.reader/.MainActivity` で起動した。
- 使用した最終 APK の SHA-256：`910620e2467a7a39059c3f2dff54ab658c28954cff79fe8a2a6ff2359b0edee3`。
- 入力：公開サンプルと、合成した 1 万項目の文書・空ファイル・不正 UTF-8 ファイルを、既存ファイルと分けた検証用のダウンロードフォルダへ ADB 転送した。画面操作は ADB と UI Automator の画面構造取得を組み合わせて行った。

| 操作と期待結果 | 実際の結果 |
| --- | --- |
| 「ファイルを開く」で標準選択画面を表示し、サンプルを選ぶ | 成功。文書名と内容を表示 |
| 日本語の見出し・本文・箇条書き・番号付きリストを表示する | 成功。画面構造と画像で確認 |
| 1 万項目の文書を縦にスクロールして末尾を表示する | 成功。通常のスワイプで表示範囲が変わり、検証用の大きなスワイプで `項目 10000` の表示を確認 |
| 選択画面から戻って取り消す | 成功。現在の文書を保持 |
| 空ファイルを開く | 成功。空であることを案内 |
| 不正な UTF-8 を開き、その後正常な文書を選び直す | 成功。読み込みエラーを案内し、再選択で正常に表示 |
| 横向きへ回転し、元の回転設定へ戻す | 成功。文書名と内容を保持 |
| 修正後のステータスバーを表示する | 成功。明るい背景で文字とアイコンを判読できる |

検証中の USB 接続時の画面点灯設定と回転設定は、検証後に元へ戻した。端末識別子、通知、個人のメモ、画面構造ファイルや画像はリポジトリ・公開レポートへ含めない。

#### ユーザーによる Dropbox 経由の手動確認

同日、ユーザーが Dropbox から端末のダウンロードフォルダへ org ファイルを保存し、本アプリの「ファイルを開く」から選択した。ユーザーから、見出し・本文・箇条書きが読める形で表示されたとの報告を受けた。これにより、実際の利用経路での保存・選択・閲覧を確認した。

この結果はユーザーの操作と報告による確認として記録し、agent によるサンプルの実機確認と区別する。個人のファイル名・内容・画像は記録しない。

GitHub 上での CI 実行と、CI 生成 APK での実機確認は未実行。

#### コミット前レビュー

- アプリ・テスト・リソース・Gradle Wrapper・ビルド設定・CI 定義・公開サンプル・文書の計 30 ファイルを確認した。追加で修正が必要な動作上の問題は見つからなかった。
- 長い文書の閲覧位置が画面再作成後も保持されることと、更新したファイルの再読み込みで古い表示が置き換わることを、画面テスト 2 件として追加した。
- `./gradlew --console=plain check assembleDebug`：成功。Debug / Release 各 19 件のテストが成功し、失敗・スキップは 0 件。Lint のエラー・警告は 0 件。
- JDK 17 と組み合わせて検証した Command-line Tools 19.0 の公式配布元と配置方法を、開発環境の準備手順に明記した。
- 公開候補にローカル専用領域、SDK、キャッシュ、APK、署名鍵が含まれないことを確認した。個人環境の絶対パスと既知の認証情報形式も検査し、該当はなかった。Wrapper JAR は公式配布値として検証済みの SHA-256 と一致した。
- 今回変更したのはテストと文書であり、アプリ本体と APK は上記の実機確認時と同一。実機確認結果はそのまま適用し、端末での再操作は行っていない。
- コミット・push・PR 作成は未実行。GitHub 上の CI と CI 生成 APK の実機確認は、引き続き後続の作業とする。
- 最終ステージ確認で Windows 用 Wrapper の CRLF 改行が空白エラーとして検出されたため、`.gitattributes` で Unix 用は LF、Windows 用は CRLF と明示した。Git 内では正規化した内容を保存し、最終のコミット対象はこの設定を含む 31 ファイルとした。
