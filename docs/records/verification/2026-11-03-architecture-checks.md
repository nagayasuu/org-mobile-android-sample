# 依存構造検査の導入・検証記録

実施日：2026-11-03（日本時間）。作成・検証：主担当 Codex agent。
初回対象：`a3b0576` を基点とする `test/architecture-rules` の未コミット差分。
実装コミット：`d7787dde5e5a2f0f784b2d5b452db852fd503c9d`。
対象ファイルは `app/build.gradle.kts`、`ArchitectureTest.kt`、README、
`docs/guides/android.md`、`docs/workflow/development.md`、本記録。

## 目的・受け入れ条件と計画

README の項目4と開発手順で決定済みの3規則を、単一モジュールのまま検査する。
本番のコンパイル済みクラスを入力し、正しい構造では成功、依存違反と対象欠落では
失敗することを受け入れ条件とする。内部クラス・Kotlin 生成クラスを含める。
アプリの実行時コード、画面、読み込み処理、既存機能テストは変更しない。

1. 既存テストと環境を確認する（V1）。
2. ArchUnit のテスト依存と3規則、対象取得の検査を追加する（V2）。
3. 意図的な違反・対象欠落を一時的に加えて検出を確認し、元へ戻す（V3）。
4. 共通検証を通し、手引き・README を実装へ合わせる（V4・V5）。
5. 別 agent へレビューを依頼する。利用できなければセルフレビューと明記し、
   差分と根拠を照合して R01〜R30の判定を残す。

ArchUnit は手順の採用方針に従う。[1.5.1 のリリース](https://github.com/TNG/ArchUnit/releases/tag/v1.5.1)、
[公式ガイドのコア API と通常のテストからの実行方法](https://www.archunit.org/userguide/html/000_Index.html)、
[Apache-2.0 ライセンス](https://github.com/TNG/ArchUnit/blob/v1.5.1/LICENSE)を確認した。
コアライブラリだけを `testImplementation` に追加し、専用 runner・プラグインを避ける。
テスト依存であり APK には同梱しない。配布元のソースや素材の転載は行わない。
既存依存全体の更新・更新確認自動化は今回の範囲に含めない。

## 実行結果

共通環境：Linux x86_64、Temurin JDK 17、Gradle 9.4.1、AGP 9.2.1、
Android SDK Platform 37.0 / Build Tools 37.0.0。
実行者は主担当 agent。環境固有の場所は記載しない。
標準環境では JDK 17 の指定と Gradle のローカルソケット利用が必要だったため、
既存の検証用 JDK・SDK・キャッシュを指定して実行した。

| ID | 対象・コマンド | 結果 |
| --- | --- | --- |
| V1 | 変更前、`./gradlew --offline --no-daemon --console=plain :app:testDebugUnitTest` | 終了0。既存結果の UP-TO-DATE 判定で成功。変更後の全テストは V4 で実行する |
| V2 | `./gradlew --offline --no-daemon --console=plain :app:testDebugUnitTest --tests 'dev.orgmobile.reader.ArchitectureTest'` | 終了0、4テスト成功 |
| V3 | 一時変更ごとに V2 と同じコマンド | 全7ケースで期待するテストのアサーション失敗と終了1を確認。下表参照 |
| V4 | `./gradlew --offline --no-daemon --console=plain check assembleDebug` | 終了0。Debug / Release 各31テスト成功（各4件の構造検査を含む）、失敗・スキップ0。Lint 成功、Debug APK 生成成功 |
| V5 | `git diff --check`、変更文書の相対リンク確認、設定との照合 | 終了0、相対リンク78件の参照先が存在。規則・依存バージョン・既存 CI の `check` と文書を照合 |

V2 の準備中、`ProtectionDomain` の null 許容警告でコンパイル失敗した。
`requireNotNull` で必須の取得情報と明示して解消した。
その後、JAR の一律除外によって AGP が渡す本番クラスが欠落し、全4テストが失敗した。
JAR を読み込み、実際のテスト出力だけを除外するよう修正して成功した。
これらは環境・テスト実装の調整であり、機能欠落による Red とは区別する。
検出能力の確認 V3 は、一時変更を用いたテスト自身の検証である。

### V3：検出能力の確認

各ケースは独立して追加し、直後に元へ戻す。コンパイル失敗ではなく、
対応するテストのアサーション失敗と終了1を確認する。

| 一時的な変更 | 期待する失敗 | 結果 |
| --- | --- | --- |
| `OrgParser.Parser` に `android.net.Uri` 型のフィールド | 解析規則 | 対応テスト失敗、終了1 |
| `OrgParser` に `java.io.File` 型のフィールド | 解析規則 | 対応テスト失敗、終了1 |
| `OrgBlock` に `android.view.View` 型を返すメソッド | 解析規則 | 対応テスト失敗、終了1 |
| `DocumentDecoder` に `android.content.ContentResolver` 型のフィールド | デコード規則 | 対応テスト失敗、終了1 |
| `ReaderViewModel.Companion` に `ContentDocumentSource` 型を返すメソッド | ViewModel 規則 | 対応テスト失敗、終了1 |
| `ReaderViewModel` に `OrgAdapter` 型のフィールド | ViewModel 規則 | 対応テスト失敗、終了1 |
| 検査パッケージを存在しない名前へ変更 | 空の対象を拒否する3規則と対象取得テスト | 全4テスト失敗、終了1 |

V3 の一時変更はすべて撤去し、`app/src/main/java` の差分がないことを確認した。
V4 の Debug / Release の XML と HTML、Lint レポートを確認した。

## 未確認・保証の範囲

- 初回ローカル検証時点では GitHub CI は未実行だった。その後、利用者から
  コミット・push・PR 作成・CI 確認・マージまでの実施依頼を受けた。
  既存の `verify` が実行する `check` に新テストを含めている。公開する際に、対象
  コミットの `verify` と `android-reports` で両ビルド種別の結果を確認する。
- 端末・利用者評価は対象外。テスト用依存と検査・文書のみで、実行時コードや UI、
  APK の依存構成に変更を加えない。
- 直接依存の静的検査であり、リフレクション・実行時のキャンセル・資源解放は
  保証しない。新しい責務・画面・プロバイダー実装やパッケージ境界を追加する際は、
  保守担当者が規則を見直す。今回の導入でレビュー負担の削減量は測定していない。

## レビュー記録

初回は別 agent の利用上限により主担当がセルフレビューを実施した。
再開後、別担当 Codex agent `review_architecture` が独立レビューを完了した。
以下は独立レビューの全30項目の判定であり、セルフレビューだけの状態を更新する。
対象は冒頭の6ファイル。実装の SHA-256 は次のとおりで、V4 後から不変。

```text
63dc30e318f8f8245a2e6f1e98f80ce2dafd2b59d7af475dc14d3bcc40d52749  app/build.gradle.kts
f8d76dde0bd2bef5b0e77b77bdfc622f3a890485e17cde89dd0d35c5cf696edc  app/src/test/java/dev/orgmobile/reader/ArchitectureTest.kt
```

## 確認根拠と実行の区別

- レビュー担当自身：status・未追跡一覧・差分・最新履歴・内容ハッシュを確認。
  `git diff --check` は終了0。変更4文書の相対リンク参照先78件の存在を再確認。
- 主担当の実行結果を直接参照：V3 の7種類の失敗ログを読み、コンパイル失敗ではなく
  `ArchitectureTest` のアサーション失敗であることを確認。
  Companion 自身の戻り型に具体実装を置いた追加検証も確認した。
- 主担当の V4 ログと最終 XML を読み、Debug / Release 各31テスト、各4件の
  ArchitectureTest、失敗・エラー・スキップ0を確認。Lint XML は問題0、APK が存在。
  全ビルドは主担当の実行結果であり、レビュー担当は再ビルドしていない。
- 公式の [ArchUnit 1.5.1 リリース](https://github.com/TNG/ArchUnit/releases/tag/v1.5.1)、
  [User Guide](https://www.archunit.org/userguide/html/000_Index.html)、
  [LICENSE](https://github.com/TNG/ArchUnit/blob/v1.5.1/LICENSE)を直接確認。

## R01〜R30

| ID | 結果 | 根拠／理由と次の確認方法 |
| --- | --- | --- |
| R01 | 確認済み | README 項目4と決定済み3規則をテスト3件と対象取得検査へ対応付けた。実行時機能の追加はない |
| R02 | 確認済み | 正しい依存、禁止型参照、空の対象、撤去後の正常復帰を V2〜V4 で直接照合 |
| R03 | 確認済み | 設定の JDK 17 / Gradle 9.4.1 / AGP 9.2.1、JUnit 4、testImplementation と記録・既存 CI を照合 |
| R04 | 確認済み | 未追跡を含む対象6ファイルを確認。app/src/main/java の差分なし。無関係な変更なし |
| R05 | 確認済み | 公式ガイドのコア import・predicate・check と依存宣言、V4 のコンパイル・実行成功を照合 |
| R06 | 確認済み | 公式ガイド・リリースを直接確認。静的な依存検査の範囲、CI 実行定義と実際の結果を区別 |
| R07 | 確認済み | Kotlin の `$` クラス名境界・null 取得時失敗を確認。内部型参照の V3 失敗、両ビルド種別での取得成功を確認 |
| R08 | 確認済み | package import→テスト出力除外→クラス群選択→禁止依存 check を追跡。ソース import 判定ではない |
| R09 | 確認済み | Parser/Block の純粋性、Decoder の JDK ストリーム許可、ViewModel の DocumentSource/URI/状態保存許可が現行コードと整合 |
| R10 | 確認済み | 決定済み ArchUnit のコアをテスト用に1件追加。専用 runner・Gradle プラグイン・新モジュールなし。3 predicate の共有は小さい |
| R11 | 対象外 | 実行時の状態変更・非同期・資源解放は変更なし。既存回帰テストの成功は V4 で確認したが実機確認へ置き換えない |
| R12 | 未確認 | 参照対象は公開コード・公式情報に限定。利用契約・AI サービスの保存/入力利用条件はレビュー担当には証拠なし。主担当が進める公式条件・設定確認へ引き継ぐ |
| R13 | 確認済み | レビュー対象差分に認証情報・個人文書/URI・環境パス・ローカル専用資料・生成物なし。今後のステージ差分・公開履歴は公開操作時に別途確認する |
| R14 | 対象外 | アプリの権限・入力検証・ファイルアクセス・送信を変更しない |
| R15 | 確認済み | TNG 公式リリース・Apache-2.0 LICENSE を直接確認。テスト依存だけで APK 同梱・素材転載なし |
| R16 | 確認済み | 期待値は公開の依存方針に由来する。禁止参照の V3 が実際に失敗し、実装出力の自己一致ではない |
| R17 | 確認済み | コンパイル済みクラスに JVM 層で適用し、正常・違反・空対象・復帰を確認。全ルートと既知内部クラスの取得を別テストで確認 |
| R18 | 確認済み | 7ケースの失敗ログと Companion 戻り型の追加確認を照合。内部/生成クラスの一律除外なし。対象欠落を成功させない |
| R19 | 確認済み | V4 実ログ・XML・Lint を直接参照。初期の null 警告と JAR 除外失敗は記録され、警告や規則を緩和していない |
| R20 | 未確認 | ローカル V4 成功は確認。GitHub の対象コミット CI は未実行。主担当が公開後 verify と android-reports を確認する。端末はテスト依存だけで対象外 |
| R21 | 対象外 | 利用者の言語・日時・入力形式に新たな制約を加えない |
| R22 | 対象外 | UI・操作・アクセシビリティの変更なし |
| R23 | 確認済み | README と手引きの規則・実行コマンド・レポート場所が実装/CI と一致し、保証の限界を説明 |
| R24 | 確認済み | 構造検査の導入だけで小さくまとまり、既存本番コードや機能テストの整理を含まない |
| R25 | 確認済み | testImplementation→通常JUnit4→check→既存verify→reports保存の連携を定義と V4 で照合 |
| R26 | 対象外 | 性能改善を主張せず、レビュー負担削減量は未計測と明記 |
| R27 | 対象外 | 保存・移行・サービス契約・APK 配布方法を変更しない |
| R28 | 確認済み | コアのみの採用、AGP のアプリ JAR を含める理由、テスト出力だけの除外、直接依存検査の限界を根拠と照合 |
| R29 | 確認済み | コードの修正必須指摘なし。古い作業状態の記録更新提案は下記。R12/R20 と公開・統合判断は主担当/保守担当者へ明示引き継ぎ |
| R30 | 確認済み | 既存責務の境界違反を通常の check で検出する価値がある。新責務の追加に伴う規則保守を手引きで明示 |

### 指摘と対応・統合前の確認

修正必須のコード指摘：なし。独立レビューはローカル実装を採用可とし、R12・R20 の
確認を主担当へ引き継いだ。古い公開未依頼・独立レビュー未実施の表現は更新した。

- R12（主担当による追確認）：共有範囲を公開リポジトリのコード・公開公式資料・
  合成データに限定し、個人文書・認証情報・ローカル専用資料を公開しない。
  [公式の Codex 向けデータ取扱説明](https://learn.chatgpt.com/docs/hipaa-configuration#codex-sign-in)で
  サインイン方法と workspace / API organization の設定による条件の違いを確認した。
  この資料は Enterprise の構成説明であり、本アカウントへの適用や個別設定は断定しない。
  保存なし・学習不使用を前提とせず、公開可能な情報のみで作業する。公開・統合は
  利用者の明示依頼の範囲で実施する。この共有範囲と公式条件の照合は確認済みとする。
- R20：公開後の対象コミットの `verify` と `android-reports` を確認し、結果は PR に残す。
  ローカル成功を CI 成功に読み替えない。
- 残るリスク：静的な直接依存以外は保証しない。新しい責務・画面・具体的な読み込み実装を
  追加する際に、保守担当者が規則と機能テストの分担を見直す。

### GitHub CI の確認と判定更新

[PR #17](https://github.com/nagayasuu/org-mobile-android-sample/pull/17) を作成し、
実装コミット `d7787dd` の [Android checks / verify](https://github.com/nagayasuu/org-mobile-android-sample/actions/runs/41596962291) が成功した。
主担当が run の対象 SHA・全ステップの成功・両成果物の保存を確認し、同じ run の
`android-reports` を取得して次を直接照合した。

- Debug / Release 各31テスト、失敗・スキップ0。`ArchitectureTest` は各4件成功。
- Lint は Error / Fatal / Warning が0件。既存の情報レベル設定により、新版通知7件を
  Hint として記録している。ローカルのオフライン検証の問題0件とは区別する。
- `org-reader-debug` と `android-reports` の取得元 SHA はいずれも実装コミットと一致。

R20 は主担当が上記 CI 結果で確認済みへ更新した。R12 は上述の公開情報のみの条件を
別 agent も再確認し、記録更新について R23 / R29 の追加指摘はなかった。
実装は V4・独立レビュー後から不変。今回の結果反映は README と本記録のみ。
最終コミットと統合後 main の CI も確認し、結果を PR へ残す。

判定：実装・独立レビュー・実装コミットの CI 確認は採用可。
最終コミットの必須 CI 成功を確認して Squash merge する。
