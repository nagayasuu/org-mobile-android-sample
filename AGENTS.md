# agent 向けの作業指示

UTF-8 の org ファイルを Android で読む閲覧アプリ。目的と利用方法は [README](README.md)、現在の動作と制約は [アプリ仕様](docs/project/app-spec.md)を参照する。

既存の未コミット変更を保つ。ローカル専用資料・設定、私的な文書の内容・ファイル名・URI、認証情報を、コミット・PR・コメント・公開ログ・CI 成果物へ含めない。ローカル専用の保存場所と公開対象の区分は [.gitignore](.gitignore)に従い、公開前に対象差分と履歴を確認する。 AI・外部ツールへ渡す情報も必要かつ許可された範囲に絞り、[レビューの情報保護項目](docs/workflow/review.md#4-情報の保護と安全な実装r12r15)に従って利用先と共有条件を確認する。

| 作業 | 読む文書 |
| --- | --- |
| 質問・調査のみ | 対象資料と関係する仕様・構造。変更がなければ検証・変更レビューを開始しない |
| ファイルの変更 | [開発手順の読み方](docs/workflow/development.md#workflow-reading)から共通事項と作業別の節を選ぶ |
| レビュー | [レビュー手順](docs/workflow/review.md#agent-review)と[R01〜R30・判定方法](docs/workflow/review.md#review-checklist) |
| Git・GitHub の操作 | [Git 運用規約](docs/workflow/git.md)の該当節。GitHub の操作は [GitHub CLI の手引き](docs/guides/github-cli.md)に従い `gh` を使う |
| 指示書・skills の変更 | 上記に加え、[指示書の保守方針とチェックリスト](docs/maintenance/agent-instructions.md) |

読む前に `rg` などで見出し・識別子を探し、該当節と関係する依存先を読む。同じ作業で対象版・内容・既読範囲を保持していれば再利用し、変更や記憶不足の箇所を読み直す。

コミット・push・PR 作成・投稿・承認・マージは依頼された操作の範囲に従い、既存の許可を重ねて確認しない。具体的な操作範囲と履歴保護は [Git 運用規約の agent の手順](docs/workflow/git.md#6-codex-が作業するときの手順)に従う。
