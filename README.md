# org-mobile-android-sample

Emacs で利用する org ファイルを Android で読むための、小さな閲覧アプリです。

Dropbox から端末へ保存した UTF-8 の `.org` ファイルを「ファイルを開く」で選択すると、見出し・本文・箇条書きを表示します。文書全体を縦にスクロールして閲覧できます。端末に保存したコピーを読むため、PC 側の更新後は再度保存してください。

最初の版は閲覧専用です。対応外の org 構文はテキストとして表示します。操作確認には [公開サンプル](examples/smoke.org) を使えます。

## 開発ドキュメント

- [開発手順](docs/development-workflow.md)：既存の動作を保ちながら、小さな実装、テスト、CI、端末確認を繰り返す手順と完了条件。
- [Android の開発環境とビルド・検証](docs/android-build.md)：環境の準備、実行コマンド、レポートと CI 成果物。
- [端末確認手順](docs/device-testing.md)：APK の導入と実際の利用経路のスモークテスト。
- [Git 運用規約](docs/git-workflow.md)：ブランチ、コミットメッセージ、PR、レビュー、統合のルール。
- [AGENTS.md](AGENTS.md)：agent が作業開始時に読む指示。

## ビルドと検証

JDK 17、Android SDK Platform 37.0、Build Tools 37.0.0 を準備し、SDK の場所を `ANDROID_HOME` またはローカル専用の `local.properties` に設定します。

```sh
./gradlew check assembleDebug
```

APK は `app/build/outputs/apk/debug/app-debug.apk` に出力します。詳しくは [環境の準備と検証コマンド](docs/android-build.md)、[USB 接続した端末での確認](docs/device-testing.md) を参照してください。初回の検証結果は [検証記録](docs/verification/2026-11-01-initial-implementation.md) に残しています。
