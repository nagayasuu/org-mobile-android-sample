# CA-008 ビルドキャッシュと検証順の評価（2026-11-19）

## 比較条件

公開の `ead5e8e92a4d0106ac3488c6a35050eda571d790` を `git archive` で別ディレクトリに展開した。Linux、Temurin 17.0.21、Gradle 9.4.1、Android SDK Platform 37.0／Build Tools 37.0.0、Robolectric 4.16（API 35）で実行した。コピー済みの依存キャッシュと専用の Gradle ユーザーホームを使い、デーモンを準備してから `--offline --console=plain --max-workers=4` で逐次計測した。元のソース・レポート・タスクキャッシュは計測対象から分離した。スクリプトの SHA-256 は `d0c99fc19329fc9493ad45774314007d752b7494391833c2b1ee93ac85c94d18`。生ログはローカルに保存した。

- **キャッシュ**。Debug 全テストで公開版 A の出力を保存。B は `OrgParser.kt` の `line.isBlank()` を等価な `line.all(Char::isWhitespace)` に変更した版。最初の A → B は B をキャッシュに入れずに無効→有効で各1回。B → A は毎回 B へ戻してから、有効→無効→無効→有効で各2回。測定対象は `:app:testDebugUnitTest` の起動から終了までとタスク状態。テストの成功を維持し、既存出力の再利用により短くなる区間を確認する。
- **実行順**。キャッシュを無効にし、`:app:testDebugUnitTest --rerun --tests <完全修飾クラス名>` で各クラスを実行。両クラスを事前に各1回実行後、JVM先行→Robolectric先行→Robolectric先行→JVM先行を、正常版と意図した失敗版で実行した。失敗版は隔離コピーの `OrgParserTest` の先頭の既存テストに `org.junit.Assert.fail("CA-008 intentional failure")` を1行加え、テストを事前にコンパイルした。実行順ごとに最初の非ゼロ終了で停止した。
- **計測と判定**。各 Gradle 呼び出しは最大120秒。経過時間は単調時計で計測し、失敗の検知時刻には失敗テスト名が出力された時点を使う。2コマンドの試行は各コマンドの所要時間を足し、計測スクリプトによる中間のログ保存時間は除く。正常時は両クラスの成功を維持し、対象テストを先に実行する既存手順が該当する失敗を早く示すかを確認する。並列化は、逐次実行で同時に返す価値のある独立した重い検証がボトルネックとして残った場合に再検討する。モデル比較・追加CI起動は評価範囲外。

## ローカルのキャッシュ比較

| 入力の遷移 | キャッシュ無効・秒 | キャッシュ有効・秒 | タスク状態 |
| --- | ---: | ---: | --- |
| A → 初回 B | 7.861 | 7.387 | 両条件とも実行4、UP-TO-DATE 28、NO-SOURCE 2、FROM-CACHE 0 |
| B → 保存済み A | 7.260／7.109 | 0.498／0.449 | 無効時は実行4、有効時は実行2・FROM-CACHE 2。どちらもUP-TO-DATE 28、NO-SOURCE 2 |

初回 B では `compileDebugKotlin`、Debug のコンパイル用・ランタイム用 JAR、`testDebugUnitTest` を実行した。B → A のキャッシュ有効時は Kotlin コンパイルとテスト出力を復元し、JAR は再生成した。B → A の中央値は無効7.185秒、有効0.474秒。A のテストは復元された試行では実行されていない。A → B は各1回でタスク状態も同じため、時間差から新規編集への効果は判断しない。

## JVM・Robolectric の時間と順序

| 条件（各2試行） | JVM先行・秒 | Robolectric先行・秒 |
| --- | ---: | ---: |
| 正常終了まで | 6.885／6.711 | 6.838／6.897 |
| 意図した JVM 失敗がログに出るまで | 0.781／0.759 | 6.728／6.847 |
| 失敗終了まで | 0.808／0.775 | 6.744／6.853 |

正常4試行では `OrgParserTest`（12件）の単独コマンドは0.745〜0.809秒、`MainActivityTest`（13件）は5.966〜6.114秒。JUnit XML のクラス時間はそれぞれ0.043〜0.046秒、5.162〜5.251秒。クラス時間と、Gradle・ワーカー起動を含むコマンド時間は計測範囲が異なる。両クラスは両順序・単独で実行できた。JVM の失敗を入れた状態でも画面側は先行時2回とも成功した。この組み合わせでは成功時の完了時間はほぼ同じで、JVM 側の失敗は先行させると中央値で約6秒早く確認できた。失敗箇所が画面側の場合や全クラスの順序独立性は、この試行からは判断できない。

同じ Gradle タスクへのクラス指定は JUnit 出力先を共有する。分割実行の各結果は当該コマンドの結果として扱う。Robolectric の別クラスには `Dispatchers.Main` の設定・復元やテスト用プロバイダーの初期化もあるため、二つのクラスを逐次で交換できたことから、同一ワーカーや共有ディレクトリでの並列実行の安全性は判断できない。CPU・ピークメモリ・共有資源の競合と総実行費用は計測していない。

## 実 CI の観測

`gh api` の attempt 別 jobs と `gh run view --attempt … --log` を照合した。秒数は GitHub が記録したジョブ／ステップの開始から終了までで、キュー・依頼からの待ち時間は含まない。全行で `verify` 成功。「テスト」は当該実行対象の Debug／Release の Gradle ログ。PR はチェックアウトした仮マージ SHA、push は先端 SHA を示す。

| 対象 | 検証 SHA | verify・秒 | ビルド・Lint・テスト・カバレッジ・秒 | テスト |
| --- | --- | ---: | ---: | --- |
| [PR #47 の起動時表示変更](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/43686048756/attempts/1) | `3ab29d84` | 165 | 108 | 両方実行 |
| [PR #51 の Robolectric 移行](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/44187550404/attempts/1) | `924039af` | 136 | 75 | 両方実行 |
| [PR #54 の成果物照合・初回](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/44319811450/attempts/1) | `8e2cacce` | 86 | 21 | 両方 FROM-CACHE |
| [同 PR の再実行](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/44319811450/attempts/2) | `8e2cacce` | 67 | 16 | 両方 FROM-CACHE |
| [CA-007 の文書変更 PR](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/44535130844/attempts/1) | `4b78af65` | 66 | 13 | 両方 FROM-CACHE |
| [同変更の main push](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/44535429279/attempts/1) | `ead5e8e9` | 92 | 18 | 両方 FROM-CACHE |

PR #47 では当該版の Debug Kotlin コンパイルが実行され、比較元の Debug テストではキャッシュ復元があった。同 PR は Robolectric 移行より前のアプリ変更なので、現行構成の対照群から外した。PR #51 はテスト構成変更を含む。残る4観測はスクリプト・文書変更または同一版の再実行で、ビルド・検証以外もジョブの大きな部分を占める。例として文書PRでは Kotlin ツール準備と Git ツールのテストが計27秒、main push では計33秒と Gradle 後処理15秒だった。コード差分・ランナー・キャッシュ状態のそろった有無比較ではないため、CI の削減率は算出しない。

CI のログ上の FROM-CACHE は Gradle による成果物復元として記録した。今回の再実行が必要な JUnit／Lint XML 集約には、引き続き [XML 再生成手順](../../guides/agent-tools.md#check-output)を使う。既存の必須 `verify`・カバレッジ判定の範囲は [検証の基準](../../workflow/verification.md#必須-ci-とブランチ保護)に従う。

## 共通検証

計測後に一時変更を戻し、元のソース・テストと一致することを確認した。隔離コピーで `--no-build-cache :app:clean check assembleDebug` が21.419秒で終了0。Debug／Releaseの各49件が再実行され、失敗・エラー・スキップは各0件。Debug Lint XMLは指摘0件で、Debug APKも生成された。今回の文書差分を対象とする CI は未実行。

全件実行時の JUnit XML のクラス時間は以下のとおり。同じ実行内の先行クラスによる初期化の影響を受けるため、単独実行の所要時間には使わない。

| クラス | 実行方式 | 件数（各ビルド種別） | Debug・秒 | Release・秒 |
| --- | --- | ---: | ---: | ---: |
| `ArchitectureTest` | JVM | 4 | 0.842 | 1.017 |
| `DocumentDecoderPropertyTest` | JVM | 1 | 0.674 | 0.734 |
| `DocumentDecoderTest` | JVM | 2 | 0.001 | 0.001 |
| `OrgParserPropertyTest` | JVM | 5 | 0.154 | 0.218 |
| `OrgParserTest` | JVM | 12 | 0.006 | 0.005 |
| `ContentDocumentSourceTest` | Robolectric | 3 | 2.846 | 2.553 |
| `MainActivityTest` | Robolectric | 13 | 2.796 | 2.345 |
| `OrgAdapterTest` | Robolectric | 2 | 0.034 | 0.035 |
| `ReaderViewModelTest` | Robolectric | 7 | 0.116 | 0.113 |

## 採否と残る観測

- **維持**。有効化済みのビルドキャッシュと、反復中に差分に関連するテストを先行させる手順を維持する。解析の変更は JVM、画面の変更は関係する Robolectric のクラスから確認する。完了前は共通検証を通す。
- **見送り**。クラス順の一律変更と並列化。今回の逐次比較では正常時に明確な差がなく、共有出力を分ける負担を負って並列方式まで導入する根拠は得られなかった。
- **試行継続**。保守担当は次の同種のソース変更3件または2026-11-30の早い方で、変更種別・対象 SHA・ローカルのタスク状態と時間・CI の run/attempt と主要ステップ時間を照合する。現行 Robolectric 構成での通常のアプリ変更は今回のローカル再現と区別して記録する。並列化を再検討する場合は、出力とプロセスの分離を含む条件で CPU・メモリ・競合・総費用も比較する。端末 E2E 高速化は廃止済みのため対象外。
