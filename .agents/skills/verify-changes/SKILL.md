---
name: verify-changes
description: このリポジトリの変更を検証するときに、差分に応じたチェックを実行し、結果と未確認事項を整理する。質問・調査だけの依頼では検証を開始しない。
---

# 変更を検証する

リポジトリのルートを作業ディレクトリとし、[AGENTS.md](../../../AGENTS.md)に従う。
検証の正本は[開発手順](../../../docs/development-workflow.md)と[Git 運用規約](../../../docs/git-workflow.md)。手順をここへ複製しない。
[作業に応じた読み方](../../../docs/development-workflow.md#workflow-reading)で必要な範囲を選び、結果の記録・出力は[agent の入力と出力を絞る](../../../docs/development-workflow.md#agent-context)に従う。

1. `git status --short`、`git diff --stat`、`git diff --cached --stat`、`git ls-files --others --exclude-standard` で全体を把握してから、対象パスの `git diff` と `git diff --cached`、新規ファイルの内容を確認する。既存の作業を保ち、対象コミットまたは未コミット差分と、今回の受け入れ条件を対応付ける。
2. 差分に合う検証を選び、実行する。
   - アプリ・テスト・ビルド設定は[ビルド・検証の手引き](../../../docs/android-build.md)の関連テストと共通検証を使う。必要な環境を確認し、実行不能なら理由を残す。
   - Git フック・メッセージ検証は[Git 運用規約の自動検証](../../../docs/git-workflow.md#自動検証と-git-フック)を使う。
   - 文書・skill の指示のみの変更は内容、ローカルリンク、差分の空白を確認する。記載したコマンド・設定は実装と照合し、補助スクリプトも変えた場合はその動作を検証する。
3. [CI と端末確認](../../../docs/development-workflow.md#5-ci-と端末で変更を確認する)が必要な範囲を判断する。CI は対象コミットと run の実際の結果を照合する。GitHub の画面・API・連携ツールも使え、`gh` を必須にしない。ローカルの成功を CI・端末の成功へ置き換えない。
4. [agent によるレビュー](../../../docs/development-workflow.md#agent-review)の実施状況を確認する。未実施ならその手順でレビューを行い、検証結果と区別して記録する。
5. [完了条件と報告](../../../docs/development-workflow.md#6-完了条件と報告)に従い、検証記録の識別子・参照先と成否、警告・未確認事項を短く返す。詳細を参照できる形に保ち、未実行の理由・次の確認方法を残す。失敗があれば報告し、成功するまでの再実行や検証の緩和で隠さない。

検証の依頼からコード修正、コミット、push、PR 投稿、承認、マージの許可を推定しない。修正も依頼されている場合はその範囲で進め、変更後に影響する検証を行う。
