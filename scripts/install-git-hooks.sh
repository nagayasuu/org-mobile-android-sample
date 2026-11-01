#!/bin/sh
set -eu

cd "$(git rev-parse --show-toplevel)"
command -v python3 >/dev/null || {
    echo 'Python 3 をインストールしてください。' >&2
    exit 1
}

if current_hooks=$(git config --get core.hooksPath); then
    if [ "$current_hooks" != '.githooks' ]; then
        echo '既存の core.hooksPath を保護するため中止しました。Git 運用規約を参照してください。' >&2
        exit 1
    fi
else
    hooks_dir=$(git rev-parse --git-path hooks)
    for hook in "$hooks_dir"/*; do
        case "$hook" in *.sample) continue ;; esac
        if [ -f "$hook" ] && [ -x "$hook" ]; then
            echo '既存の有効なフックを保護するため中止しました。Git 運用規約を参照してください。' >&2
            exit 1
        fi
    done
fi

chmod +x .githooks/pre-commit .githooks/commit-msg
git config --local core.hooksPath .githooks
echo 'Git フックを有効にしました（この clone のみ）。'
