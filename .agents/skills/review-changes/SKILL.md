---
name: review-changes
description: このリポジトリの差分レビューや完了前の agent レビューを行うときに、R01〜R30の判定と根拠を記録する。調査や一般的な質問だけでは使わない。
---

# 変更をレビューする

リポジトリのルートで [AGENTS.md](../../../AGENTS.md) と[作業に応じた読み方](../../../docs/development-workflow.md#workflow-reading)に従い、[agent レビュー手順](../../../docs/development-workflow.md#agent-review)を実行する。確認者の選択・対象版の固定・根拠の直接確認・必要な検証・再確認・結果の保存は、この正本に集約する。

[記録方法とR01〜R30の本文](../../../docs/development-workflow.md#review-checklist)を読み、全件の判定と根拠を残す。入力・返答は [agent の入力と出力](../../../docs/development-workflow.md#agent-context)に従い、指摘・未確認事項・残るリスク・総合判定を返す。

レビュー担当は対象ファイルを変更しない。外部への投稿や Git 操作は依頼された範囲に従い、レビュー依頼だけから許可を推定しない。
