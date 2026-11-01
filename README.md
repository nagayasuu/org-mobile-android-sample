# org-mobile-android-sample

Emacs で利用する org ファイルを Android で読むための、小さな閲覧アプリです。

Dropbox から端末へ保存した UTF-8 の `.org` ファイルを「ファイルを開く」で選択すると、見出し・本文・箇条書きを表示します。文書全体を縦にスクロールして閲覧できます。端末に保存したコピーを読むため、PC 側の更新後は再度保存してください。

最初の版は閲覧専用です。対応外の org 構文はテキストとして表示します。操作確認には [公開サンプル](examples/smoke.org) を使えます。

## 開発ドキュメント

- [開発手順](docs/development-workflow.md)：最小の機能を実装し、ビルド、テスト、CI、端末での動作確認につなげる手順。
- [Git 運用規約](docs/git-workflow.md)：ブランチ、コミットメッセージ、PR、レビュー、統合のルール。
- [AGENTS.md](AGENTS.md)：agent が作業開始時に読む指示。

## ビルドと検証

JDK 17、Android SDK Platform 37.0、Build Tools 37.0.0 を準備し、SDK の場所を `ANDROID_HOME` またはローカル専用の `local.properties` に設定します。

```sh
./gradlew check assembleDebug
```

APK は `app/build/outputs/apk/debug/app-debug.apk` に出力します。環境の準備、検証結果、USB 接続した端末へのインストール方法は [開発手順](docs/development-workflow.md#現在の整備状況と実行コマンド) にまとめています。
