# 優先度「中」の手法の確認・試行・採否

## 目的・順序・受け入れ条件

[対象メモ](../notes/codex-adoption-recommendations.md#このプロジェクトで活用できる手法)の「中」9項目を上から確認し、既存の仕組みで不足する補助を追加した。条件付きのLSP・ASTや設定変更は必要性を確認して採否を決め、未実施を導入済み・改善実績としない。アプリ・依存・個人設定・認証・料金方式は変更しない。

| 順序 | 対応・確認結果 | 採否・残る確認 |
| --- | --- | --- |
| 1 MCP | CLI 0.166.0で登録0件・有効0件を確認。必要なツールだけを探し、説明を必要時に取得する運用を継続 | 無効化対象なし。ChatGPT側の接続や全ツール定義量まで確認した意味ではない。個人設定・接続先は転載しない |
| 2 キャッシュ | 固定した同一プロンプトのCLI 2試行で、各15,653入力のうち12,288がキャッシュ入力。各78.50% | キャッシュ利用を確認。今回の手順変更による因果的な効果や費用削減率は未測定。固定指示を安定させる方針を維持 |
| 3 履歴圧縮 | 再開用メモを追加し、既読範囲をハッシュ照合できる補助を実装 | 標準圧縮とメモを利用。実際の圧縮前後の総入力・再読比較は未実施で、しきい値を変更しない |
| 4 構造検索 | OrgParserの関連候補7ファイル、ReaderViewModelは4ファイル。定義と関連テスト、必要な原文へ到達 | rgと範囲読取を継続。LSP・ASTは未導入。境界・呼出先を追加読取でも確定できない場合に比較導入する |
| 5 段階化 | 計画様式へ探索・修正・検証の終了条件、探索を広げる条件、再開メモへの引き継ぎを追加 | 運用として利用。探索量の自動配分は未実装で、必須検証・レビューを維持 |
| 6 ファイル記憶 | context_memory.pyを追加。既読行・識別子・全内容と列挙依存先のSHA-256を.localへ保存し、変更・削除・不正UTF-8で再利用を拒否 | 必要時の補助として採用。ファイル再読によるハッシュ計算自体は行い、未列挙依存先や環境の変更は別途確認 |
| 7 簡素化 | 集計JSONの--compactを追加。実測2試行のJSONは2,167→1,467文字で、全フィールド・値が一致 | 任意利用。文字数だけの結果で、トークン数・速度の削減率は未測定。プロンプトの意味や条件を落とす圧縮は行わない |
| 8 設定比較 | gpt-6.1-solに固定し、同じ合成文書をhigh/mediumで各1回。期待値と使用量は同一 | 推論強度を下げる利点なし。既定設定は変更しない。モデル横断・verbosityは候補と対応範囲・予算を固定して次回比較 |
| 9 再利用 | 既存のsetup-gradleを確認。新しい既読記録を実ソースで保存・照合し、既存XML鮮度テストを含む全Python検証を実行 | 既存キャッシュを維持。Gradleの実行速度やCIでのhitは未計測。過去のXML・検証結果を今回の成功にしない |

## 対象・環境

HEAD `a60344b`、ブランチ `docs/codex-adoption-recommendations` の未コミット作業に追加。Linux、Python 3.13.16、Git、Codex CLI 0.166.0。前回までの差分を保ち、無関係な `docs/notes/agents-md-draft.md` は読取・編集対象外。作成者は主担当Codex agent。

今回の対象は新規 `scripts/context_memory.py`・`scripts/tests/test_context_memory.py`・`docs/templates/agent-handoff.md`、更新した `scripts/summarize_usage.py`・`scripts/tests/test_adoption_tools.py`・`docs/development-workflow.md`・`docs/templates/implementation-plan.md`・対象メモと本記録。

| 対象ファイル | SHA-256（レビュー依頼時） |
| --- | --- |
| scripts/context_memory.py | d005ca3d336c215e12a0b759a24b1d5d616f8ff650ae519668e296e3073826b6 |
| scripts/tests/test_context_memory.py | 4d74808b02726e11e98252f62995c5a0bbe07192dc0523b4330d85b7fd98d39c |
| scripts/summarize_usage.py | 30ea2135936bc590bb7224ea2584dbf83a8db42ac0dde415af4462c36cdcd9d2 |
| scripts/tests/test_adoption_tools.py | d4fd686b368431d47f5dadab1383dadd91015f67c30b4fcceccfb7dd38ab4797 |
| docs/development-workflow.md | 972f93ead78142e12281045b989f3e5e9ac560b4c65ae9b832550e012f13c942 |
| docs/templates/implementation-plan.md | a490b0fe15f595f45f1b59bb56a4b77a047393af669276f597af7cb7ade29488 |
| docs/templates/agent-handoff.md | c2ff8d40c043050d006c95973f17fd51f0c6e7c40e1c80303bfc1b44d8dccdf4 |
| docs/notes/codex-adoption-recommendations.md | 5cf8e35078f695dcfcb3f9d0fe294f7508fed22aed144fde6058a9e4c78ed90d |

本記録の最終版もレビュー時に固定する。今回のローカル記録は原文を含まず、依存先とハッシュを利用者が正しく列挙することを前提にする。Gitルート・公開対象の境界を確認し、.local以外への記録、既存記録の上書き、Git除外対象・.git・リポジトリ外の入力を拒否する。意図的な記録改ざんや読了の有無を保証する署名・監査機能ではない。

## 検証結果

主担当の実行。生ログはGit除外の.local/checks/に置く。新しいPython依存は追加していない。

| ID | 結果 | コマンド・確認範囲 |
| --- | --- | --- |
| V1 | 確認済み | `run_check.py --output-dir .local/checks/adoption-medium-baseline -- python3 -m unittest discover -s scripts/tests -q`：既存67件成功 |
| V2 | 確認済み | `run_check.py --output-dir .local/checks/adoption-medium-memory-final -- python3 -m unittest discover -s scripts/tests -p test_context_memory.py -q`：Gitルート・公開境界・ハッシュ・依存先・範囲・不正記録・上書き拒否を検証 |
| V3 | 確認済み | `run_check.py --output-dir .local/checks/adoption-medium-compact -- python3 -m unittest discover -s scripts/tests -p test_adoption_tools.py -q`：compactの全値一致・1行出力と既存集計を確認 |
| V4 | 確認済み | `python3 scripts/run_check.py --output-dir .local/checks/adoption-medium-final-2 -- python3 -m unittest discover -s scripts/tests -q`：終了0、全74件成功。変更後の不正UTF-8でもstaleとなる境界を含む |
| V5 | 確認済み | OrgParserの既読1〜65行とOrgParserTestのハッシュを実リポジトリでsave/checkしunchangedを確認。ソースは変更していない |
| V6 | 確認済み | 下記の合成文書2試行のJSONLをsummarize_usage.pyで集計。通常表示とcompactのJSON値が一致 |
| V7 | 確認済み | document_tools.py check：追跡32文書・205リンク成功。メモ・再開様式・本記録をパス指定し3文書・18リンク成功。git diff --check終了0。context changeも15,810文字で既定上限内、R01〜R30を保持 |
| CI | 未確認 | リモート操作未依頼のため未実行。公開時に既存CIのPython検証と対象SHAを確認する |
| Androidビルド・E2E | 対象外 | アプリ・ビルド設定・端末の利用経路を変更していない。キャッシュの実ビルド速度比較も今回は未実施 |

## CLIの小規模試行

モデルは既存の評価でも使ったgpt-6.1-solに固定した。公開の合成文書だけを渡し、同じプロンプト・期待値をhigh→mediumの順に各1回、最大45秒ずつ実行する条件をローカルの実行スクリプトに固定した。永続設定を変更せず、`codex exec --json --ephemeral --sandbox read-only --skip-git-repo-check --model gpt-6.1-sol --config 'model_reasoning_effort="high"'` のように実行ごとに指定した。mediumはその値だけを変更した。ツール・ファイル・追加agentを使わないよう指示し、イベントもモデル応答のみであった。空の一時作業ディレクトリで実行し、プロジェクトの私的ファイルは渡していない。

固定した入力は次のとおり。プロンプトSHA-256は `8ba3b6e1e9efea867fce0a8c7da828b932efe1d02a106444161051a8718bfc45`。

```text
Correct only 確認しましす to 確認します in the text below. Return the complete corrected text exactly without code fences or commentary. Do not use tools, run commands, access files, or start agents.

# 手順
結果を確認しましす。
```

期待値は見出しと本文をそのまま残し「結果を確認します。」へ直した全文。外側の検査で、前後の空白を除いた完全一致を判定した。これは実装・レビューまでの課題成功ではなく、合成文書修正の応答一致だけを評価したsmoke試行である。

| 条件 | 終了・期待値一致 | 入力 | キャッシュ入力（内数） | 出力 | 観測した秒数 |
| --- | --- | ---: | ---: | ---: | ---: |
| high | 終了0・一致 | 15,653 | 12,288 | 13 | 4.982 |
| medium | 終了0・一致 | 15,653 | 12,288 | 13 | 4.933 |

両実行ともturn.completedが各1件。元のusageにreasoning_output_tokensは0であり、出力へ再加算していない。各1回・固定順・既存キャッシュありのため、時間差の優劣、一般的な成功率、highが不要であることを保証しない。プロジェクトの解析・画面・独立レビューはこの試行では実行していない。費用と外側の準備・確認・全担当の使用量は未計測であり、料金の概算や全体削減率を出さない。

通常の制限内の最初のCLI起動は、読み取り専用制約でモデル実行前に終了1、usageなしとなった。権限付き実行では既存認証のまま上記2試行が成功した。最初の失敗は別の起動条件として.local/checks/adoption-medium-model/に保持し、成功0・usage不完全・成功あたりの値nullとして集計した。許可した2試行を超える追加のモデル実行は行っていない。成功側のマニフェスト・JSONL・集約値は.local/checks/adoption-medium-model-permitted/に保存し、公開しない。

## 採否・残る課題

ハッシュ記録とcompact、再開・段階化の様式は必要時の補助として利用する。MCPの無効化、Kotlin専用検索、強制圧縮、既定モデル・推論設定の変更を、今回の結果だけを理由に導入しない。[評価と継続改善](../development-workflow.md#codex-adoption-evaluation)に従い、保守担当が次の3件の同種作業または月末の早い方で再読・追加取得・手戻り・保守負担を確認する。

圧縮前後、LSP・AST、モデル横断・verbosity、実ビルドキャッシュの比較は、上表の必要性や対応環境・予算を固定できた時点で保守担当が実施する。これらの未実施を完了済みと扱わず、品質が低下したり再試行・保守負担が増える場合は任意化・撤回する。

CLIのMCP・設定・JSONLの仕様は[公式MCP仕様](https://learn.chatgpt.com/docs/extend/mcp)、[設定一覧](https://learn.chatgpt.com/docs/config-file/config-reference)、[非対話実行](https://learn.chatgpt.com/docs/non-interactive-mode)を今回開いて照合した。使用量の価格換算やモデル横断の推奨は行っていない。共有範囲は[既存の利用者確認](2026-11-07-instruction-reading.md#別-agent-によるレビュー)と前回の継承の範囲内の公開資料・必要差分・合成入力に限定し、個別の保存条件を監査したという意味にはしない。

## レビュー記録

作成者は主担当Codex agent、確認者は別のCodex agent review_adoption。セルフレビューではない。対象は上表8ファイルと、結果転記前の本記録（SHA-256: e2cfc7c6063a07fb22f7c2f4659cab25d27e91cac16fd9591a6913a206becefe）。確認者は対象を編集せず、原文・差分・ハッシュと根拠を照合した。以下は主担当による結果の転記である。

確認者自身の全74テスト、追跡32文書・205リンク、新規3文書・18リンク、git diff --checkはすべて成功。成功2試行のusage・イベント種別・期待応答一致、起動失敗側の欠測/null集計、compactの全値一致と2,167→1,467文字、contextの15,810文字も直接確認した。MCP件数は主担当の観測として区別し、個人設定は読み直していない。

| ID | 判定 | 根拠・理由 |
| --- | --- | --- |
| R01 | 確認済み | 中9項目を順に整理し、実装・試行・未実施を区別。 |
| R02・R07 | 確認済み | 変更・削除・不正UTF-8、範囲・形式不正、上書き拒否を実装とテストで確認。 |
| R03 | 確認済み | Python標準ライブラリとGitのみで既存要件と整合。 |
| R04 | 確認済み | 対象・ハッシュ・状態を確認し、無関係な既存文書を除外。 |
| R05 | 確認済み | CLI実行結果と公式MCP・設定仕様を照合。 |
| R06 | 確認済み | キャッシュ率・応答一致・文字数を費用・品質・総入力の改善と区別。 |
| R08〜R10 | 確認済み | 既存Repository境界を再利用し、記録・集計・様式の責務と採用理由が明確。 |
| R11・R14 | 確認済み | 保存・読取・ハッシュ比較を追跡。公開境界、.local限定、排他的作成、原文非出力を確認。 |
| R12 | 確認済み | 既存利用者確認を同じ環境の公開資料・必要差分・合成入力だけへ継承。 |
| R13 | 確認済み | 公開対象に個人設定・認証情報・生イベントの転載を認めず。 |
| R15 | 対象外 | 新規依存・外部コード・素材の持込みなし。 |
| R16〜R18 | 確認済み | 固定期待値で無効化・公開境界・異常系、compactの意味保持、外側からの応答一致を検証。 |
| R19 | 確認済み | ハッシュ・作成者記録と独立した74テストを照合。MCP件数は作成者の観測として区別。 |
| R20 | 未確認 | ローカル検証成功。公開時の必須CI確認が必要。Androidビルド・E2Eはアプリ変更なしのため対象外。 |
| R21・R23 | 確認済み | 日本語UTF-8、状態と終了コード、再読・再取得の説明が動作と整合。 |
| R22 | 対象外 | UI変更なし。 |
| R24・R25 | 確認済み | 補助CLI・テスト・正本・様式・記録の整合とリンクを確認。 |
| R26 | 確認済み | 同じJSON値で比較。モデル試行は各1回・固定順と明記し優劣を一般化していない。 |
| R27 | 確認済み | 記録の版を検査。不正記録は拒否し、既存記録を上書きせず再生成可能。 |
| R28・R29 | 確認済み | 任意補助としての採否、未実施、担当・次回確認・撤回条件を記録。 |
| R30 | 確認済み | 原文確認・必須検証を保ち、古い記録の再利用や出力短縮による誤判断を防ぐ。 |

修正必須の指摘・改善提案：なし。判定は変更内容は採用可、統合はCI未確認のため保留。未列挙依存・環境変更の検出外と未実測の課題は、上記の保守担当と再検討条件へ引き継ぐ。コミット・push・PR投稿・マージは行っていない。
