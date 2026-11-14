# Kotlinの宣言読取と探索量の配分

[開発手順](development-workflow.md#必要性を確かめて使う検索既読記録設定比較)から必要なときに使う補助である。通常の検索・原文確認・必須検証を維持する。ツールはアプリや個人のCodex設定を変更しない。

## Kotlinの宣言を構文木から取得する

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

## 不足のフィードバックで探索候補を広げる

`scripts/exploration_plan.py` は、追跡済みの公開Kotlinファイルに対する文字列一致から候補パス・行範囲・内容ハッシュを返す。原文や意味解析の結果は返さない。未追跡ファイルは対象外なので、必要なら既存の検索で個別に確認する。このツールのためだけにファイルをステージしない。

```sh
python3 scripts/exploration_plan.py .local/exploration/parser.json OrgParser
python3 scripts/exploration_plan.py .local/exploration/parser.json OrgParser --feedback insufficient
python3 scripts/exploration_plan.py .local/exploration/parser.json OrgParser --feedback sufficient
```

初回は候補3件・2,000文字、不足なら6件・4,000文字、さらに不足なら12件・8,000文字へ自動配分する。文字数内に収めるため候補数を減らす場合も省略件数を返す。上限でも不足ならmanual_investigationと終了1を返し、自動拡大を止める。検索条件や追加ツールを見直す。状態は.localにのみ保存し、他の目的や別クエリーの記録を上書きしない。

sourceの変更・追加・削除をハッシュ一覧で検出した場合はneeds_recheckと終了1、配分を初期状態に戻し、古い充足判断を引き継がない。候補なしはno_matchesと終了1、不正入力は終了2。十分というフィードバックによるready_for_editは呼出者の申告であり、理解や品質の証明ではない。参照範囲と依存先を読んだ後、[計画の終了条件](templates/implementation-plan.md#手順と検証)で編集へ進むか判断する。

候補数・文字数の配分であり、トークン予算や必須レビューの量を自動変更しない。追加取得・再読・ツール呼出しを[評価様式](templates/codex-adoption-evaluation.md)へ記録し、総量や手戻りが増える場合は通常の検索へ戻す。
