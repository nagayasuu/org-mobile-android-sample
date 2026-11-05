# org-mobile-android-sample

Emacs で利用する org ファイルを Android で読むための、小さな閲覧アプリです。

Dropbox から端末へ保存した UTF-8 の `.org` ファイルを「ファイルを開く」で選択すると、見出し・本文・箇条書きを表示します。文書全体を縦にスクロールして閲覧できます。端末に保存したコピーを読むため、PC 側の更新後は再度保存してください。

最初の版は閲覧専用です。対応外の org 構文はテキストとして表示します。操作確認には [公開サンプル](examples/smoke.org) を使えます。

## 開発ドキュメント

- [開発手順](docs/development-workflow.md)：既存の動作を保ちながら、小さな実装、テスト、CI、E2E を繰り返す手順と完了条件。
- [レビューチェックリスト](docs/development-workflow.md#review-checklist)：セルフレビューと PR レビューで使う30項目。結果と根拠は [PR テンプレート](.github/pull_request_template.md)へ記録する。
- [agent によるレビュー](docs/development-workflow.md#agent-review)：対象差分を指定して30項目を確認する手順と依頼文。別 agent による確認とセルフレビュー、実行結果と未確認を区別する。
- [Android の開発環境とビルド・検証](docs/android-build.md)：環境の準備、実行コマンド、レポートと CI 成果物。
- [Git 運用規約](docs/git-workflow.md)：ブランチ、コミットメッセージ、PR、レビュー、統合のルール。
- [AGENTS.md](AGENTS.md)：agent が作業開始時に読む指示。

## ビルドと検証

JDK 17、Android SDK Platform 37.0、Build Tools 37.0.0 を準備し、SDK の場所を `ANDROID_HOME` またはローカル専用の `local.properties` に設定します。

```sh
./gradlew check assembleDebug
```

APK は `app/build/outputs/apk/debug/app-debug.apk` に出力します。詳しくは [環境の準備と検証コマンド](docs/android-build.md)、[自動 E2E の手順](docs/android-build.md#自動-e2e-テスト) を参照してください。初回の検証結果は [検証記録](docs/verification/2026-11-01-initial-implementation.md) に残しています。

カバレッジ計測と CI と同じ判定には `python3 scripts/run_coverage.py --base-ref main` を使います。対象・出力先・比較条件は[カバレッジ計測の手引き](docs/android-build.md#カバレッジ計測)を参照してください。

`OrgParser`・`DocumentDecoder` のプロパティベーステストは、Kotest Property と JUnit 4 で6つの性質を各1,000例検証し、通常の検証と PR の CI に含まれます。対象・入力上限・seed による再現方法は[プロパティベーステストの手引き](docs/android-build.md#プロパティベーステスト)を参照してください。

同じ2クラスへの PIT ミューテーションテストを手動で実行できます。試験で見つかった検証不足を具体例テストで補い、31件すべての検出を確認しました。最低スコアは100%とし、CI への追加は継続運用後に再判断します。コマンドと制約は[ミューテーションテストの手引き](docs/android-build.md#ミューテーションテスト)、比較結果と判断理由は[導入記録](docs/verification/2026-11-04-mutation-tests.md)を参照してください。

標準ファイル選択を通す自動 E2E は `./gradlew :app:pixel2Api37DebugAndroidTest` で手動実行します。API 37 の専用エミュレーターで、表示・長文末尾、取り消し・回転後の保持、不正 UTF-8・空文書からの復帰、更新後の再読み込み、1万項目、表示設定・アクセシビリティの計8シナリオを確認します。CI の `Android E2E` も手動実行です。環境・結果の見方は[自動 E2E の手引き](docs/android-build.md#自動-e2e-テスト)を参照してください。
