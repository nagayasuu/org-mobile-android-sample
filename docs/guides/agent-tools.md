# agent ツールの手引き

文書取得、探索、ログ保存、既読管理、使用量集計の実行方法と限界。必要なツールの節だけを読み、必須検証・レビューの基準は workflow の各文書に従う。

## Codex skills

このリポジトリの skill は、正本の手順へ案内して検証・レビュー・E2E を進める入口とする。手順本文と判定基準は [開発文書の案内](../README.md)に示す workflow の各正本に集約する。

| skill | 使用する場面 |
| --- | --- |
| [verify-changes](../../.agents/skills/verify-changes/SKILL.md) | 差分に応じた検証を実行し、結果と未確認事項を整理する |
| [review-changes](../../.agents/skills/review-changes/SKILL.md) | R01〜R30によるレビューと根拠を記録する |

Codex はリポジトリの `.agents/skills/` から skill を検出する。明示的に使う場合は、例えば `$verify-changes 今回の変更を検証して` と依頼する。検出・読み込みの仕様は[公式資料](https://learn.chatgpt.com/docs/build-skills)を参照する。Git の共有対象は上表の2つの `SKILL.md` のみとし、`.agents/` 内のその他の資料・設定は引き続き除外する。

補助として次の公開 skill をユーザー領域に導入できる。共有の開発手順をこれらの skill のインストールに依存させない。取得元を固定し、更新時は内容と互換性を確認する。

| skill | 提供元・取得対象 | 用途 |
| --- | --- | --- |
| android-profiler | [android/skills の固定版](https://github.com/android/skills/tree/6daa53ef27fa2aa87827d183a85c06cedceca833/profilers/android-profiler) | トレース・メモリなどの記録と解析 |
| android-cli | [android/skills の固定版](https://github.com/android/skills/tree/6daa53ef27fa2aa87827d183a85c06cedceca833/devtools/android-cli) | Android CLI による環境・端末の操作 |
| gh-fix-ci | [openai/skills の固定版](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/gh-fix-ci) | `gh` による失敗した PR チェックの調査 |

再導入は Codex の `$skill-installer` に上表の固定版 URL を渡して依頼する。独自 skill から公開 skill の内容を複製せず、公開 skill は取得元のライセンスを保ってユーザー領域へ導入する。skill の導入と必要な実行ツール・接続の準備は区別する。Android CLI、SDK・`adb`、計測ツール、GitHub CLI の認証などは作業に応じて別途確認する。

`gh-fix-ci` は `gh` と認証を前提とし、標準の手順では修正計画への承認後に実装する。利用者が許可した範囲と既存の許可を確認して使う。この skill を利用できない場合も、[GitHub CLI の手順](github-cli.md#github-cli)に従って調査を進める。各 skill を導入したことだけで CI・端末・性能の検証を完了扱いにしない。

<a id="agent-context"></a>

## agent の入力と出力を絞る

1. **必要な範囲を探してから読む。** ファイル名・見出し・識別子を検索し、該当する節・関数とその依存先を読む。同じ担当が同じ作業で版・範囲を保持している間は再取得せず、不足した節をまとめて追加する。探索結果もまず候補のパスや該当行に絞る。出力が切り詰められたら未読の範囲を確認し、検索条件や読取範囲を狭めて補う。
2. **中間データを実行側で処理する。** 一覧の絞り込み、件数・ハッシュの計算、機械的な照合はシェルやコードで行い、判断に必要な結果を返す。必要なツールの説明を選んで読み、検索対象と無関係なツール定義や資料をまとめて取り込まない。
3. **検証の結果と詳細を分ける。** 実行者、対象版、環境、コマンド、終了コード、成否、警告・未確認事項、詳細の参照先を一か所へ記録し、`V1` などの識別子で参照する。成功時の表示は短くし、失敗時は原因を調べられる箇所を示す。長いログは出力先で保持し、必要な箇所を読む。出力の短縮で失敗・警告を隠さず、パイプや後続処理で元の終了コードを失わない。ログにもローカル専用情報や秘密情報を含めない。
4. **レビューへ必要な情報を渡す。** [依頼文のひな形](../workflow/review.md#review-request)を使い、目的、受け入れ条件、対象版・差分、関連ファイル、検証記録、未確認事項を渡す。会話全体や生ログを一律に転記しない。レビュー担当は原文・差分・実行結果を直接確認し、返答では各 ID の判定と根拠、指摘と残るリスクを中心に記す。同じ根拠は参照し、作成者の説明を繰り返さない。
5. **再開に必要な状態を残す。** 長い作業や引き継ぎでは、目的・受け入れ条件、ブランチ・対象版、変更ファイル、決定事項と理由、検証記録、未解決事項、次の操作を作業メモへまとめる。依頼された操作の範囲も残し、再開時は現在の差分と照合する。要約だけで不足する事実は原文で確認する。メモは共有手順の代わりにせず、公開する根拠とローカル専用情報を区別する。

この手順は、読み込み・出力・再調査の重複を減らすためのものである。検証やレビューを減らすために使わない。確認者は[agent レビュー手順](../workflow/review.md#agent-review)で選び、追加のサブエージェントは独立した調査の必要性と受け渡しの負担から判断する。主担当の文脈が短くなっても、全 agent の合計トークン数が減るとは限らない。

導入後は同種・同程度の作業で、取得できる場合の入力・出力トークン数、文書の再読・出力切り詰めの回数、レビュー後の手戻りを比べる。利用モデル、対象版、作業範囲、測定できない項目も記録し、サブエージェント分を含める。キャッシュによる再計算・費用の削減はトークン数の削減と区別し、未計測の削減率を保証しない。採用の継続は、保守担当者が次の同種作業の結果から判断する。

使用量を取得できない agent がある場合は、親スレッドの数値と全体を区別し、完全な総入力の削減率を算出しない。確認者の選択や実行形態が異なる試行は分けて評価する。

検索結果はまずパスまたは該当行を返し、初回の目安を40行・8,000文字とする。候補が多ければ対象ディレクトリ・識別子を絞るか、原文を `.local/` に保存し、[抜粋ツール](#check-output)で必要な範囲を取得する。上限はトークン数ではなく文字数であり、未取得範囲と追加取得の回数を残す。重要な依存先やエラーが未読なら、範囲を変えて追加取得する。

再開・レビュー用のメモは[依頼文](../workflow/review.md#review-request)の項目を用い、各検証を `V1` などの ID と保存先で参照する。本文や生ログを複製せず、読取済みファイルの SHA-256 と節・行範囲も必要に応じて添える。再開時にはハッシュと現在の差分を照合し、変更された範囲と不足する依存先を原文で読む。常時読む AGENTS.md と skill は入口のままにし、実行方法は本書、規則と判定基準は workflow の各正本へ集約する。

使用量集計の入力形式・測定値の意味は、必要なときに[専用の節](#成功1件あたりの使用量を集計する)を読む。運用を見直す場合は[評価手順](../maintenance/evaluation.md#codex-adoption-evaluation)に従う。

<a id="document-tools"></a>

## 文書検証と節の取得に共通ツールを使う

Python 3.10 以上と Git があれば、標準ライブラリだけで次を実行できる。

```sh
# 追跡済み Markdown 全体。未追跡の新規公開文書はパスを明示して別途確認する
python3 scripts/document_tools.py check
python3 scripts/document_tools.py check docs/workflow/development.md

# 見出しの完全一致、生成アンカー、または明示的なアンカー ID で取得する
python3 scripts/document_tools.py read docs/guides/agent-tools.md agent-context

# 共通事項と既知の作業別節を一度に取得する。重なる行は一度だけ返す
python3 scripts/document_tools.py context change --max-chars 32000 \
  --include docs/guides/agent-tools.md document-tools \
  --include docs/guides/agent-tools.md check-output

# 同じ作業・同じ担当で続ける場合だけ、返却済み範囲の記録を任意で使う
python3 scripts/document_tools.py context change --max-chars 32000 \
  --include docs/guides/agent-tools.md document-tools \
  --state .local/context/task-author.json --reader task-author

# 追加取得も上と同じstate/readerで実行。既返却部分は省き、未返却部分を返す
python3 scripts/document_tools.py context change \
  --include docs/guides/agent-tools.md check-output \
  --state .local/context/task-author.json --reader task-author

# 別のレビュー担当は独立した記録で原文を取得する
python3 scripts/document_tools.py context review \
  --state .local/context/task-reviewer.json --reader task-reviewer

# 記録なしの従来の取得も維持する
python3 scripts/document_tools.py context change
python3 scripts/document_tools.py context review
```

移動・削除をまだステージしていない場合、既定の `check` は削除済み追跡パスの欠落も報告する。新規文書を含む現在の公開 Markdown 全体を検査するには、リポジトリルートで次を実行する。Git の追跡済みと非除外の未追跡パスから現存ファイルだけを選ぶ。非ゼロ終了は検証の失敗として扱う。

```sh
python3 - <<'PY_CHECK'
from pathlib import Path
import subprocess

result = subprocess.run(
    ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', '*.md'],
    check=True, capture_output=True,
)
paths = sorted({name for name in result.stdout.decode('utf-8').split('\0')
                if name and Path(name).is_file()})
if not paths:
    raise SystemExit('No public Markdown files found')
raise SystemExit(subprocess.call(['python3', 'scripts/document_tools.py', 'check', *paths]))
PY_CHECK
```

この例はローカルリンクの存在も検査するため、削除した文書への未修正の参照は失敗になる。リンク以外のパス表記、同リポジトリの GitHub URL、内容の意味は別途確認する。

`check` は UTF-8、末尾改行・末尾空白、ローカルリンク先、Markdown のアンカーを検査する。外部 URL の到達性や内容・意味の正しさは確認しない。既定では Git の追跡済み Markdown のみを読み、指定パスでもリポジトリ外・Git 除外対象・`.git` は拒否する。新規ファイルを含む検証では公開可能なパスだけを指定する。リンク削除や見出し変更では、全体検証で参照元も確認する。

対象の書式は ATX 見出し（`#`〜`######`）、日本語の見出し、単独の `<a id="…"></a>`、インラインリンクと参照形式のリンクである。フェンス内の見出し・リンクと HTML コメントは解析対象から除く。Setext 見出し・複雑に入れ子になった Markdown・HTML のリンクは対象外であり、その書式を追加する場合は原文確認とツール拡張を行う。GitHub 上の表示との完全な互換性を保証しない。

`read` は対象の子見出しを含め、次の同階層以上の見出しまで原文を返す。先頭にパス・ファイル内容の SHA-256・取得範囲、本文に元の行番号を付ける。複数 ID を指定したときは重なる行を一度だけ返す。存在しない節・曖昧な見出し・文字数上限超過は非ゼロ終了とし、本文を部分的に返さない。既定の上限は16,000文字で、必要なら子見出しを選ぶか `--max-chars` を明示する。依存先や必須読取範囲は利用者が追加取得し、ツールで取得した範囲だけで全確認が済んだとは判断しない。

`context` は AGENTS.md 全文、開発手順の読み方・完了条件、検証基準の共通検証、本書の入力と出力、レビュー手順の agent レビュー・チェックリスト全節（記録と判定を含む）、Git 運用の基本方針・Codex の手順を各正本から取得する。`change` は変更の共通手順も含める。`--include PATH SECTION [SECTION ...]` を繰り返して作業別の節もまとめられる。同じファイルの要求を統合し、親子・別名・重複指定で重なる行は一度だけ返す。行番号とファイル全体のSHA-256を残し、要約には置き換えない。

`--state` と `--reader` は任意で、同じ作業・同じ担当に返した文書のSHA-256と行範囲だけを `.local/` に記録する。本文は保存しない。保存先はGitルートの除外済み・未追跡パスに限り、別readerの記録は拒否する。同じSHAの返却済み行は本文を省き、メタデータに省略範囲を示す。新しい要求範囲は返し、ファイルが変わればその文書の旧範囲を再利用しない。全要求が返却済みなら `status: unchanged` と範囲・ハッシュだけを返す。無変更のたびに繰り返す必要はなく、範囲追加や版確認が必要な場合にだけ実行する。

この記録は返却の履歴であり、読了・理解や担当者の認証を証明しない。別作業・別agent・新しいセッションでは別のstate/readerを使う。同じ記録を並列更新しない。ツールや読取方法の変更、記憶不足、出力切り詰めで原文を保持していない場合は `--refresh` を同じコマンドへ追加して全要求範囲を取得し直す。下流での切り詰めは自動検知できない。編集前の原文確認、独立したレビュー、必要な依存先や必須検証を省略する根拠にしない。

全要求とstateを先に検証し、欠落・曖昧さ・UTF-8不正・最終出力の合計24,000文字上限超過などの入力エラーでは、本文を返さずstateも更新しない。標準出力の書出し・flush失敗時もstateを進めない。保存の確定時にI/O障害が起きた場合は、本文が届いていても非ゼロ終了し、古い記録を維持する。失敗を成功扱いにせず原因を確認する。上限不足なら必要な依存先を削る代わりに、取得を分けるか `--max-chars` を明示する。

通常操作は上記の例を使い、`--help` やツール本文・使い方の再確認は、例にない操作・引数エラー・版変更がある場合に限って必要な範囲で行う。初回取得では固定見出しをツール内で検索するため、同じ共通事項の本文検索と再掲を重ねない。未知の節は `rg -n '^#{1,4} ' 対象.md` などで見出しだけを先に確認する。質問・調査のみでは既存の検索・選択読解を使い、検証・レビューを開始しない。

検証ログの保存と JUnit・Lint レポートの集約は[ログ保存と結果集約](#check-output)を使う。変更を作成した担当と別のレビュー agent を起動する場合は、親会話全体を複製せず、[依頼文](../workflow/review.md#review-request)の情報で開始できる方法を選ぶ。必須の別 agent レビュー・原文確認は維持し、起動方法や全担当の使用量を取得できなければ未確認として残す。独立した次の作業を新しいセッションへ渡す場合も同じ引き継ぎ情報を使い、継続作業の再調査を増やす一律のセッション分割は行わない。

## 成功1件あたりの使用量を集計する

`scripts/summarize_usage.py` は、明示したローカル JSONL だけを読み、入力・キャッシュ済み入力・出力と成功率を集計する。アカウント設定や会話保存領域は探索しない。[公式の非対話実行の資料](https://learn.chatgpt.com/docs/non-interactive-mode)にある `codex exec --json` の `turn.completed.usage`（`input_tokens`、`cached_input_tokens`、`output_tokens`）を使う。実際の使用版・取得形式を確認し、対応しない形式を独自推定で補わない。生イベントにはコードや会話が含まれ得るため `.local/` に保存し、公開するのは確認済みの集約値だけとする。

次は入力マニフェストの形式例である。`.local/usage/trials.json` などに作成し、`events` はマニフェストからの相対パスで、各担当の重複しない完全な実行ログを指定する。取得できない担当も省略せず `events: null` で残す。`agents_complete` は全担当を列挙できた場合だけ true にする。費用は別途確認した USD の総額を担当ごとに入力し、不明なら null にする。料金の自動推定や契約料金への換算はしない。

```json
{"trials": [{
  "id": "docs-before-01", "condition": "before", "task_kind": "docs",
  "revision": "対象SHAと差分ハッシュ", "environment": "固定した環境とCLI版",
  "model": "実際のモデル", "reasoning_effort": "実際の設定",
  "review_mode": "separate-agent", "success": true, "agents_complete": true,
  "agents": [
    {"id": "author", "events": "author.jsonl", "cost_usd": null},
    {"id": "reviewer", "events": "reviewer.jsonl", "cost_usd": null}
  ]
}]}
```

```sh
python3 scripts/summarize_usage.py .local/usage/trials.json > .local/usage/summary.json
```

1試行は、決めた課題を開始して受け入れ条件とレビューを判定するまでとする。途中の再試行もその担当のログに含め、成功・失敗した試行を両方列挙する。`success` はイベントの正常終了ではなく、検証とレビューに基づき実行者が判定する。同じ課題群（文書修正・解析修正・画面修正）と受け入れ条件を前後で固定し、各条件を同じ回数反復する。課題の内容・対象・検証 ID・未確認事項は別の作業メモで参照できるようにする。新しい作業を勝手に実行するベンチマーク機能は持たない。

集計は condition・task_kind・revision・environment・model・reasoning_effort・review_mode ごとに分ける。条件をそろえた群同士だけを比較し、失敗試行も含む総入力・総費用を成功試行数で割る。キャッシュ済み入力は入力の内数とし、再加算しない。同一パスの再利用・重複 ID・負数・不正形式はエラーにする。ログのコピーや一部重複は自動検出できないため実行者が排除する。欠測、未完了、使用量のない失敗ターンがあれば observed_tokens は観測分だけを示し、総入力の成功あたりの値は null にする。成功0件、費用不明の場合も該当する成功あたりの値は null とし、0として扱わない。

このセッションで取得できない使用量や費用は未確認として残す。合成イベントによる集計ツールの検証は削減効果の実測ではない。実作業の比較結果が得られるまで、導入による削減率や費用改善は主張しない。

試行には任意で `task_id` と `measurements` を加えられる。[評価様式](../templates/codex-adoption-evaluation.md)にある秒数・回数・文字数のキーだけを受け付け、省略・nullは未計測、0は観測した0を示す。回数・文字数・最初の編集までの入力トークンは非負整数、秒数は有限の非負数とする。未知のキーや不正値はエラーにし、従来のマニフェストもそのまま使える。

出力には試行 ID・課題 ID・成功判定、未キャッシュ入力とキャッシュ率を加える。全担当の使用量が不完全なら未キャッシュ入力とキャッシュ率も null とする。measurements は1件以上観測した指標だけを返す。各指標に観測数・欠測数を示し、欠測があれば合計・中央値・p95を null にする。全件観測かつ20試行以上の場合のみ、昇順の `ceil(0.95 × 件数)` 番目をp95として返す。この件数は表示上の目安で、統計的な保証ではない。全件欠測の指標はキーを省略し、未計測を意味する。成功率が同じでも失敗課題が入れ替わっていないか、trial_results と[継続評価](../maintenance/evaluation.md#codex-adoption-evaluation)の台帳を照合する。

## 必要性を確かめて使う検索・既読記録・設定比較

MCPは作業に必要なツールだけを検索し、説明も必要時に取得する。ローカルCLIの設定と、ChatGPT側の接続や独自APIの設定を区別する。[CLIのMCP仕様](https://learn.chatgpt.com/docs/extend/mcp)の `enabled_tools` などを使う場合も、対象版・必要な操作・設定変更の権限を確認する。登録0件を別のクライアントの接続0件や、全ツールの入力負担0と解釈しない。接続先・コマンド・環境変数・個人設定を公開記録へ転記しない。

キャッシュは同じ作業中の固定指示・ツール構成を安定させ、[使用量集計](#成功1件あたりの使用量を集計する)のcache_ratioと総入力を別々に確認する。キャッシュ率が高いことだけで指示量や再読が減ったと判断しない。長期作業では標準の履歴圧縮を基本とし、[再開用メモ](../templates/handoff.md)へ対象版・決定・検証・未解決事項・次の操作を残す。自動圧縮のしきい値や認証・料金方式はこの手順だけで変更しない。

コードの探索は[実装計画](../templates/implementation-plan.md)の段階と終了条件を用いる。パスと識別子を先に絞り、定義・関連テスト・依存先を確認する。同名関数や呼出先を既存検索で確定できない場合に、KotlinのLSP・AST導入を別の小さな比較として検討する。テキスト検索を構文解析や完全な呼出関係の保証として扱わず、追加読取でも境界を確定できなければツール調査へ戻る。

必要なら[宣言読取と探索量の配分](agent-tools.md)を使う。Kotlinの構文木による原文取得と、候補不足のフィードバックによる配分拡大を提供する。どちらも任意の補助とし、意味解析や理解、必須検証の十分性を保証するものではない。

既読範囲と内容ハッシュは、Python標準ライブラリとGitによる `context_memory.py` で記録できる。

```sh
# 実際に読んだ行範囲だけを指定する。依存先は必要に応じて追加する
python3 scripts/context_memory.py save .local/memory/parser-001.json \
  app/src/main/java/dev/orgmobile/reader/OrgParser.kt --start 1 --end 65 \
  --identifier OrgParser.parse --depends app/src/test/java/dev/orgmobile/reader/OrgParserTest.kt
python3 scripts/context_memory.py check .local/memory/parser-001.json
```

記録には原文を保存せず、公開対象パス・全内容のSHA-256・既読行範囲・識別子・依存先のハッシュを保存する。出力先は `.local/` 内に限定し、既存記録を上書きしない。Gitルート以外からの実行、Git除外対象・`.git`・リポジトリ外の入力、不正な範囲・形式は拒否する。ソースか列挙した依存先が変更・削除されたらstaleと終了1を返し、再利用できる行範囲を返さない。不正入力は終了2にする。unchangedでも読了・理解・今回の十分性を証明するものではなく、編集前は原文を確認する。列挙していない依存先・設定・ツール版の変更は検出しないため、環境と対象版も引き継ぐ。

この仕組みはファイルを読んでハッシュを再計算するため、ローカルI/Oの省略や解析成果物の高速化を保証しない。モデルへの原文再掲が必要か判断するための補助であり、古いテスト・JUnit/Lint XMLを今回の検証結果として再利用する機能ではない。Gradleのビルドキャッシュは既存の `setup-gradle` とGradle自身の入力判定に従い、XML集約時の[鮮度要件](#check-output)を維持する。

使用量集計の `--compact` は同じ全フィールド・値を保ち、整形用空白だけを省略する。必要ならファイルへ保存して使い、人が確認しやすい表示も残す。文字数の短縮をトークン・時間の削減率へ換算しない。プロンプトや報告も目的・制約・受け入れ条件・根拠を保って短くし、条件が落ちたり追加質問が増えたりするなら元へ戻す。

モデル・推論強度・出力長は[評価様式](../templates/codex-adoption-evaluation.md)で一要因ずつ比較する。[設定仕様](https://learn.chatgpt.com/docs/config-file/config-reference)と使用版で対応を確認し、既存設定ファイルを書き換えず実行ごとの引数で試す。モデル横断比較やverbosityは使用可能な候補と対応範囲を固定してから行い、非対応値を指定して比較したと扱わない。単純な合成文書の一致だけで、このアプリの解析・画面課題や必須レビューを通す能力を保証しない。成功・失敗・起動失敗・使用量欠測を分け、利点が確認できなければ既定設定を維持する。

## Kotlinの宣言読取と探索量の配分

[開発手順](#必要性を確かめて使う検索既読記録設定比較)から必要なときに使う補助である。通常の検索・原文確認・必須検証を維持する。ツールはアプリや個人のCodex設定を変更しない。

### Kotlinの宣言を構文木から取得する

`scripts/kotlin_symbols.py` は、関数・クラス・objectなどの宣言を列挙し、字句上の修飾名から原文の行を取得する。型解決や完全な呼出関係を提供するLSPではない。同名・オーバーロードは曖昧なまま選ばず、修飾名や宣言の開始行で指定する。

Linux・CPythonで検証した準備例。CコンパイラーとGitHub CLIを使い、Python依存は隔離環境だけへ入れる。Tree-sitter本体は0.26.1、Kotlin文法はfwcd/tree-sitter-kotlinのコミット `d6af96d2e23ef0a8ff5ab512864378cf08fba311` に固定する。両方ともMITライセンスであり、配布元は[Pythonバインディング](https://github.com/tree-sitter/py-tree-sitter)と[文法の固定版](https://github.com/fwcd/tree-sitter-kotlin/tree/d6af96d2e23ef0a8ff5ab512864378cf08fba311)。アプリへ組み込む依存ではない。

```sh
bash scripts/setup-kotlin-tools.sh

.local/kotlin-tools/venv/bin/python scripts/kotlin_symbols.py \
  app/src/main/java/dev/orgmobile/reader/OrgParser.kt \
  --grammar-library .local/kotlin-tools/kotlin.so --list
.local/kotlin-tools/venv/bin/python scripts/kotlin_symbols.py \
  app/src/main/java/dev/orgmobile/reader/OrgParser.kt \
  --grammar-library .local/kotlin-tools/kotlin.so --symbol OrgParser.Parser.parse
```

`--grammar-library` はネイティブコードを読み込むため、上記のように提供元と版を確認して作ったライブラリだけを指定する。セットアップは未使用の.local配下にだけ作成し、既存環境を上書きしない。Python開発ヘッダーは不要。文法はすべてのKotlin構文を保証しない。構文木にエラーがあれば宣言を部分的に返さず非ゼロ終了し、既存の検索と原文読取へ戻す。

出力にはソース・文法ライブラリのSHA-256、パーサー版、元の行番号とバイト範囲を付ける。行出力は元の行全体を返すため、同じ行に複数宣言がある場合の正確な範囲はstart_byte/end_byteでも確認する。既定8,000文字を超える出力、不一致・曖昧な名前、不正UTF-8、Git除外対象・.git・リポジトリ外は本文を返さない。編集前には現在の原文を確認する。

任意依存のテストは次のように実行する。通常のPython環境ではKotlin用テストをskipし、未検証として区別する。CIのverifyでは同じセットアップを行い、Kotlin用テストも実行する。

```sh
KOTLIN_GRAMMAR_LIBRARY="$PWD/.local/kotlin-tools/kotlin.so" \
  .local/kotlin-tools/venv/bin/python -m unittest discover -s scripts/tests -p test_kotlin_symbols.py -q
```

### 不足のフィードバックで探索候補を広げる

`scripts/exploration_plan.py` は、追跡済みの公開Kotlinファイルに対する文字列一致から候補パス・行範囲・内容ハッシュを返す。原文や意味解析の結果は返さない。未追跡ファイルは対象外なので、必要なら既存の検索で個別に確認する。このツールのためだけにファイルをステージしない。

```sh
python3 scripts/exploration_plan.py .local/exploration/parser.json OrgParser
python3 scripts/exploration_plan.py .local/exploration/parser.json OrgParser --feedback insufficient
python3 scripts/exploration_plan.py .local/exploration/parser.json OrgParser --feedback sufficient
```

初回は候補3件・2,000文字、不足なら6件・4,000文字、さらに不足なら12件・8,000文字へ自動配分する。文字数内に収めるため候補数を減らす場合も省略件数を返す。上限でも不足ならmanual_investigationと終了1を返し、自動拡大を止める。検索条件や追加ツールを見直す。状態は.localにのみ保存し、他の目的や別クエリーの記録を上書きしない。

sourceの変更・追加・削除をハッシュ一覧で検出した場合はneeds_recheckと終了1、配分を初期状態に戻し、古い充足判断を引き継がない。候補なしはno_matchesと終了1、不正入力は終了2。十分というフィードバックによるready_for_editは呼出者の申告であり、理解や品質の証明ではない。参照範囲と依存先を読んだ後、[計画の終了条件](../templates/implementation-plan.md#手順と検証)で編集へ進むか判断する。

候補数・文字数の配分であり、トークン予算や必須レビューの量を自動変更しない。追加取得・再読・ツール呼出しを[評価様式](../templates/codex-adoption-evaluation.md)へ記録し、総量や手戻りが増える場合は通常の検索へ戻す。

<a id="check-output"></a>

## 検証コマンドのログ保存と結果集約

Python 3.10 以上と Git が必要である。`scripts/run_check.py` を使うと、コマンドの標準出力・標準エラーを全文保存し、モデルへ返す通常出力を成否・終了コード・保存先に絞れる。リポジトリのルートで実行し、実行ごとに未使用の出力先を指定する。

```sh
python3 scripts/run_check.py --output-dir .local/checks/python-001 -- \
  python3 -m unittest discover -s scripts/tests -q

# XML レポートも集約する場合は、この実行で再生成する
python3 scripts/run_check.py --output-dir .local/checks/android-001 \
  --junit 'app/build/test-results/testDebugUnitTest/TEST-*.xml' \
  --junit 'app/build/test-results/testReleaseUnitTest/TEST-*.xml' \
  --lint app/build/reports/lint-results-debug.xml -- \
  ./gradlew --console=plain --rerun-tasks check assembleDebug
```

出力先には `command.log` と `summary.json` を保存する。集約 JSON はコマンド、UTC 開始時刻、所要時間、HEAD、追跡済み未コミット差分のハッシュ、元の終了コード、指定レポートの参照先、テスト数・失敗ケース・スキップ数、Lint 重大度別件数を保持する。未追跡ファイルの内容は差分ハッシュに含まれないので、レビューへ渡す対象一覧・内容ハッシュは別途記録する。

`passed` は実行したコマンドが終了0で、指定した XML の確認にも問題がないことだけを示す。JUnit・Lint の指定がなければ、そのレポートの確認はしていない。指定したレポートの欠落・不正形式・実行開始より古い更新時刻は `unconfirmed` と非ゼロ終了にし、古い結果を成功根拠にしない。通常の Gradle 実行は UP-TO-DATE で XML を再生成しない場合があるため、XML を指定するときは上の例のように再生成する。mtime の確認だけで生成元の真正性まで保証しない。

元コマンドの非ゼロ終了コードを優先して返す。POSIX のシグナル終了は `command_returncode` に負の元値を保存し、ツールの終了コードには128＋シグナル番号を使う。元コマンドが終了0でも、JUnit の failure/error、Lint の Error/Fatal、レポート確認の失敗は終了1にする。Lint の Warning・Information・Hint などとテストのスキップは件数を表示し、既存の Gradle・Lint の合否基準を変更しない。シェルを介さず引数列を実行し、ログ保存先を上書きしない。失敗時は `command.log` の該当箇所と元のレポートを読み、原因を確認する。

ログ・コマンド引数・レポートにはローカル専用情報や秘密情報を含めない。`.local/` は Git の除外対象であり、ログを CI 成果物や PR へ自動登録しない。公開する場合は確認済みの非機密な集約値だけを既存の検証記録へ記載する。機密情報の自動除去機能はない。

保存したログや検索結果は、次のように必要な範囲を取得する。

```sh
python3 scripts/read_excerpt.py .local/checks/python-001/command.log --lines 40
python3 scripts/read_excerpt.py .local/checks/python-001/command.log --tail --lines 40
python3 scripts/read_excerpt.py .local/checks/python-001/command.log --match FAILED --before 3 --lines 20
python3 scripts/read_excerpt.py .local/checks/python-001/command.log --start 41 --lines 40
```

`read_excerpt.py` は UTF-8 の原文を変更せず、行番号、全文の SHA-256、総行数、取得範囲、省略行数を返す。既定は40行、メタデータ・行番号を含め8,000文字までであり、トークン上限ではない。上限超過、不正 UTF-8、検索文字列の不一致では本文を返さず非ゼロ終了する。長い1行の場合は `--max-chars` を明示して増やす。`--match` は正規表現ではなく最初の文字列一致から前後を取得し、前の行は最大 `--lines - 1` 行とする。空ファイルや末尾より先の範囲は本文が空になる。省略箇所に必要な情報があれば `--start` などを変えて原文を追加取得する。このツールも機密情報を自動除去しない。
