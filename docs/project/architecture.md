# アーキテクチャ

現在の実装の責務と依存関係を示す。動作の仕様は [アプリ仕様](app-spec.md)、構造を変更するときの判断基準は [設計変更の判断基準](../workflow/design.md)を参照する。

## コードとテストの配置

アプリは単一の `:app` モジュールとして一つの APK に含めて配布する。主なコードは `app/src/main/java/dev/orgmobile/reader/`、JVM・Robolectric テストは `app/src/test/`、端末上の E2E は `app/src/androidTest/` に置く。

| 責務 | 実装 | 受け渡すもの |
| --- | --- | --- |
| ファイル選択・画面と操作 | [MainActivity](../../app/src/main/java/dev/orgmobile/reader/MainActivity.kt) | 選択 URI を ViewModel へ渡し、状態を表示する。閲覧位置を保持する |
| 表示状態・読み込みの制御 | [ReaderViewModel](../../app/src/main/java/dev/orgmobile/reader/ReaderViewModel.kt) | DocumentSource から読み、文書・読み込み中・失敗の状態を公開し、成功した URI を保存する |
| 読み込みの境界・Android の URI アクセス | [DocumentSource / ContentDocumentSource](../../app/src/main/java/dev/orgmobile/reader/DocumentSource.kt) | URI からストリームと表示名を取得し、文書を返す。ストリームとカーソルを解放する |
| 文字コード変換 | [DocumentDecoder](../../app/src/main/java/dev/orgmobile/reader/DocumentSource.kt) | ストリームを UTF-8 として解釈し、不正な入力を拒否して解析へ渡す |
| org 解析・表示用の値 | [OrgParser / OrgBlock](../../app/src/main/java/dev/orgmobile/reader/OrgParser.kt) | テキストを見出し・本文・リストなどの値へ変換する |
| 文書ブロックの表示 | [OrgAdapter](../../app/src/main/java/dev/orgmobile/reader/OrgAdapter.kt) | OrgBlock の一覧を画面の項目へ対応付ける |

## 読み込みと状態の流れ

標準ファイル選択 → MainActivity → ReaderViewModel → DocumentSource → ContentDocumentSource → DocumentDecoder → OrgParser の順で読み込み、結果を状態として画面へ返す。Android OS・文書プロバイダーはアプリの外部依存である。

ReaderViewModel は IO dispatcher で読み込み、次の読み込み時に前の job をキャンセルする。失敗の状態反映にもキャンセル確認を行う。キャンセル後の古い結果の反映を防ぐことと、同期プロバイダーの読み込み自体が即時停止することは区別する。画面回転とプロセス再作成の保証も同一視せず、保存した URI による再読み込みと閲覧位置の扱いを関係するテストで確認する。

## 維持する依存方向

OrgParser と OrgBlock は Android・画面・ファイルアクセスの実装に依存しない。DocumentDecoder は Android・画面・プロバイダーに依存せず、JDK のストリームと文字コード処理を使う。ReaderViewModel は画面や ContentDocumentSource の具体実装ではなく、DocumentSource に依存する。

これらは [ArchitectureTest](../../app/src/test/java/dev/orgmobile/reader/ArchitectureTest.kt)で検査する。検査対象・合否と変更時の条件は [依存構造の検証基準](../workflow/verification.md#依存構造を自動検査する)、コマンドは [Android の手引き](../guides/android.md#依存構造の検査)に従う。ソース上の依存検査だけでは、プロバイダーの遅延や資源解放などの実行時の保証を証明しない。
