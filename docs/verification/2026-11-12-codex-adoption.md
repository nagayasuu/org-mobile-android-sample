# Codex 活用の優先度「高」への対応記録

## 目的・受け入れ条件・実施順序

[対象メモ](../notes/codex-adoption-recommendations.md#このプロジェクトで活用できる手法)の「高」8項目を上から確認し、既存の仕組みを維持して不足を補う。アプリ・依存・アカウント設定は変更しない。公開手順と Python 標準ライブラリだけで再現でき、未取得の使用量を0や改善実績にしないことを受け入れ条件とした。

1〜3は見出し検索・既読範囲再利用・read/context・run_check の既存実装を確認した。4の抜粋機能を追加して検証した後、5の関連テスト選択、6の短い入口構成、7の引き継ぎを確認・文書化した。最後に8の CLI イベント集計と比較手順を追加した。実際の前後比較は使用量・費用の欠測により未実施であり、ツール導入と効果の実証を区別する。

## 対象版・環境

作成者は Codex agent。ブランチ `docs/codex-adoption-recommendations`、HEAD `a60344b` に対する未コミット差分。Python 3.13.16、Linux、Git を使用。対象は次の6ファイルと本記録。既存の未追跡 `docs/notes/agents-md-draft.md` は対象外であり、参照・変更していない。対象メモは依頼前から未追跡で、今回の変更はローカルリンク、4・8の現状説明、末尾の対応結果である。先行する一般提案の技術調査をやり直す変更ではない。

| ファイル | SHA-256（レビュー依頼時） |
| --- | --- |
| scripts/read_excerpt.py | 8ac519b41557ebf3e02cf58ba9a237539739eb9a7a295224f55a9a1b899b3d47 |
| scripts/summarize_usage.py | a68704b40040c34768347e99aaf7a8f608a8bd1cf858db969e06467a47f4961e |
| scripts/tests/test_adoption_tools.py | 1fb68d15da86b042922c87c3286a831cc7e006fe94ff1d9b98fd8dd8ed0ab314 |
| docs/development-workflow.md | 29f5350139d5d0e82d82950480763ddebb94d23ca6e2443aaf8b0f0ce1eb3e79 |
| docs/android-build.md | 1b55a9d3c72f439eec4a8891f84bffdd1f010bd8d20b9823476dbbd4d6e938dd |
| docs/notes/codex-adoption-recommendations.md | 916f1499771b1c235169454b3d851cce8be6b7eac521bb409bcf43572f2dd94d |

## 検証結果

すべて作成 agent によるローカル実行。実行ログは Git 除外対象の `.local/checks/` に置き、公開記録へ生ログを転載しない。

| ID | 結果 | 実行・確認内容 |
| --- | --- | --- |
| V1 | 確認済み | `python3 scripts/run_check.py --output-dir .local/checks/adoption-baseline -- python3 -m unittest discover -s scripts/tests -q`：終了0、既存58テスト成功。 |
| V2 | 確認済み | `document_tools.py read docs/android-build.md check-output --max-chars 6000` と `context change` をファイルへ取得。終了0。初回の出力は1,873文字・14,852文字。最終版の context change も既定の文字数上限内で終了0。これはトークン計測ではない。 |
| V3 | 確認済み | `run_check.py --output-dir .local/checks/adoption-excerpt -- python3 -m unittest discover -s scripts/tests -p test_adoption_tools.py -q`：終了0。先頭・末尾・文字列周辺・指定行、SHA-256と行番号、省略行数、上限超過時に本文を返さない動作を確認。 |
| V4 | 確認済み | `run_check.py --output-dir .local/checks/adoption-usage -- python3 -m unittest discover -s scripts/tests -p test_adoption_tools.py -q`：終了0。合成イベントで複数ターン・失敗試行・別 agent の合算、条件分離、成功0件・費用欠測・使用量欠測・未完了・不正入力・二重計上の拒否を確認。 |
| V5 | 確認済み | `python3 scripts/run_check.py --output-dir .local/checks/adoption-final-python -- python3 -m unittest discover -s scripts/tests -q`：終了0、全64テスト成功。新規6テストを含む。 |
| V6 | 確認済み | 追跡済み Markdown の `python3 scripts/document_tools.py check`：32文書・192ローカルリンク成功。`git diff --check`：終了0。新規公開文書は `python3 scripts/document_tools.py check docs/notes/codex-adoption-recommendations.md docs/verification/2026-11-12-codex-adoption.md` で2文書・10リンク成功。 |
| CI | 未確認 | リモート操作は未依頼のため未実行。push 後に既存 Android CI の Python 検証と文書検証を確認する。 |
| Android ビルド・E2E | 対象外 | Python 補助ツールと文書だけの変更で、アプリ・端末経路を変更していない。 |

CLI の対応イベントは[公式資料](https://learn.chatgpt.com/docs/non-interactive-mode)を確認した。集計ツールは明示されたファイルだけを読み、会話保存領域やアカウント設定を探索しない。外部サービスへの送信や追加依存はない。

## レビュー記録

作成者：Codex agent（主担当）。確認者：別の Codex agent `review_adoption`。セルフレビューではない。確認者は対象原文・差分・上記6ファイルの内容ハッシュを直接照合し、対象ファイルは変更していない。主担当が本節へ結果を転記した。対象は上記 HEAD と内容ハッシュに固定した差分・新規ファイルで、本記録のレビュー結果転記はその後の追記である。

確認者自身の実行は、Python全64テスト、追跡済み32文書・192リンク、新規2文書・10リンク、`git diff --check` で、すべて成功した。作成者の V1・V3・V4・V5 は summary.json とログ末尾を直接照合した。イベントの3キーは公式資料とも照合した。共有対象の必要性は本依頼の公開リポジトリの変更範囲に照合したが、利用先の保存・入力利用条件の確認記録はないため R12 は未確認として扱う。

| ID | 判定 | 根拠・理由 |
| --- | --- | --- |
| R01 | 確認済み | 高8項目の対応表と正本文書・CLI追加が受け入れ条件に対応する。8の実測は未確認として区別。 |
| R02・R07 | 確認済み | UTF-8不正、抜粋上限、不一致、不正数値、欠測、未完了、成功0件を実装とテストで確認。 |
| R03 | 確認済み | Python標準ライブラリのみで、公開手順のPython 3.10以上と整合。 |
| R04 | 確認済み | status、ステージ差分、対象一覧・ハッシュを照合。無関係な既存文書は除外。 |
| R05 | 確認済み | CLIと公式イベント形式を照合し、ローカル実行に成功。 |
| R06 | 確認済み | 合成イベントの検証と実測改善を区別し、欠測から削減率を主張していない。 |
| R08〜R10 | 確認済み | 抜粋と集計の責務が独立し、read/context/run_checkを維持。追加依存なし。 |
| R11・R14 | 確認済み | 明示ファイルの読取から出力まで追跡。入力を変更せず、集計失敗時は本文を返さない。 |
| R12 | 未確認 | 利用先の保存・入力利用条件の公開確認記録がない。判断権限を持つ利用者が適用範囲を確認する必要がある。 |
| R13 | 確認済み | 指定対象の差分・公開記録に秘密情報や私的資料の混入を認めず、生ログを転載していない。 |
| R15 | 対象外 | 新規依存・外部コード・素材の持込みなし。AI利用条件はR12で判定。 |
| R16〜R18 | 確認済み | 手計算可能な期待値で失敗試行・別担当・キャッシュ内数・条件分離を検証。失敗時のstdout空も確認。 |
| R19 | 確認済み | ハッシュと作成者ログを照合し、別agent自身も全64テスト成功。テストの削除・緩和なし。 |
| R20 | 未確認 | CIは未実行で、push後に必須CIの確認が必要。アプリ変更がなくAndroidビルド・E2Eは対象外。 |
| R21・R23 | 確認済み | 日本語UTF-8、行番号、文字数上限、nullの意味が説明と整合。追加取得方法も記載。 |
| R22 | 対象外 | UI変更なし。 |
| R24・R25 | 確認済み | 2つの独立CLIと文書・テストの範囲。使用例、入力形式、出力、リンクを照合。 |
| R26 | 対象外 | 性能・費用改善の実測主張なし。比較は取得可能になった時点で行う。 |
| R27 | 対象外 | 既存保存形式、移行、外部サービス、配布方法の変更なし。 |
| R28 | 確認済み | 標準ライブラリによる追加の採用理由を確認。全担当列挙・コピー重複排除の限界を明示。 |
| R29 | 確認済み | 修正必須なし。未確認と改善提案を区別し、次の比較条件を記録。 |
| R30 | 確認済み | 原文への追跡性を保って出力を制限し、欠測を改善実績と誤認しない価値がある。 |

修正必須の指摘：なし。改善提案（R17・R18）：`test_adoption_tools.py` に、空ファイル・末尾超過・`--before >= --lines` の期待値を追加すると境界の回帰検出を強められる。現時点の実装不具合ではなく、今回の受け入れ条件を確認する64テストが成功しているため、主担当は今回は見送った。保守担当が抜粋の範囲選択を変更する際に再検討する。

総合判定：**未確認のため保留**。ローカル実装・検証に修正必須の指摘はないが、R12の利用条件と統合時の必須CI確認が残る。agentの判定を利用者の権限やGitHubの承認の代わりにしない。

## 残る課題と Git 操作

実使用量・費用と同じ課題群による反復比較は未確認。保守担当が全担当分のイベント・費用・受け入れ結果を取得できた時点で比較する。未取得の値を推定で埋めず、削減率は主張しない。コピーされたログや部分重複は自動検出できないため、利用者が重複しない入力を選ぶ。

コミット・push・PR 投稿・マージは行っていない。既存の未コミット作業を維持する。
