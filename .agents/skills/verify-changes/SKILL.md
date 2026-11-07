---
name: verify-changes
description: このリポジトリの変更を検証するときに、差分に応じたチェックを実行し、結果と未確認事項を整理する。質問・調査だけの依頼では検証を開始しない。
---

# 変更を検証する

リポジトリのルートで [AGENTS.md](../../../AGENTS.md) と[作業に応じた読み方](../../../docs/development-workflow.md#workflow-reading)に従い、[変更の共通手順](../../../docs/development-workflow.md#change-steps)で対象・受け入れ条件を確かめ、[共通の検証](../../../docs/development-workflow.md#共通の検証)と作業別の参照先から検証を選んで実行する。

[agent レビュー](../../../docs/development-workflow.md#agent-review)の実施状況を確かめ、結果を検証と区別する。記録は [agent の入力と出力](../../../docs/development-workflow.md#agent-context)、返答は[完了条件と報告](../../../docs/development-workflow.md#6-完了条件と報告)に従う。成否・未確認事項・詳細の参照先を返し、未実行を成功扱いにしない。

検証のみの依頼から、コード修正やコミット・push・PR 投稿・承認・マージの許可を推定しない。
