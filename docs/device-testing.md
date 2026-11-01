# 端末確認手順

[開発手順](development-workflow.md)で決めた受け入れ条件を、実際の Android 環境で確認する。環境とビルドコマンドは[Android の開発環境とビルド・検証](android-build.md)を参照する。

## 確認対象を決める

標準の確認環境は Pixel 10a／Android 17 とする。別の端末やエミュレーターを使った場合は、その環境と未確認の差を記録する。変更した機能の受け入れ条件と、以下の既存機能のスモークテストを組み合わせる。

CI の対象コミットと成功した run を確認し、その run の APK を取得する。取得した APK の SHA-256 は次のように計算し、インストールするファイルと記録を対応させる。CI 成果物を使う場合は、コマンドのパスを取得したファイルに置き換える。

```sh
sha256sum app/build/outputs/apk/debug/app-debug.apk
```

公開サンプルや合成データを使い、個人のメモを操作・画面取得の対象にしない。端末設定を変更する場合は元の設定を控え、確認後に戻す。

## USB 接続した端末でのスモークテスト

1. Pixel 10a／Android 17 の開発者向けオプションで USB デバッグを有効にし、開発用 PC に接続する。端末に表示される接続許可を確認する。
2. 接続状態を確認する。複数台ある場合は、以降の `adb` コマンドで `-s` を使い対象を明示する。`unauthorized` の場合は端末側で許可する。

```sh
adb devices
```

3. GitHub Actions の `org-reader-debug` 成果物から取得した `app-debug.apk` をインストールする。CI の成果物がまだない場合は、ローカルビルドした APK を次のように使い、確認記録で区別する。

```sh
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n dev.orgmobile.reader/.MainActivity
```

ローカル版と CI 版の Debug APK は署名が異なる場合がある。`INSTALL_FAILED_UPDATE_INCOMPATIBLE` になった場合、この閲覧アプリを `adb uninstall dev.orgmobile.reader` で削除してから、確認対象の APK をインストールする。閲覧状態とファイルへのアクセス権はリセットされるため、ファイルを選び直す。端末のダウンロードフォルダにある org ファイルは残る。

4. Dropbox に公開可能なサンプル [`examples/smoke.org`](../examples/smoke.org) を置き、Dropbox アプリから端末のダウンロードフォルダに保存する。
5. 本アプリで「ファイルを開く」を押し、標準の選択画面で保存したファイルを選ぶ。日本語、見出し、本文、箇条書き、番号付きリスト、末尾の本文を確認する。
6. もう一度選択画面を開いて取り消し、現在の文書が残ることを確認する。画面を回転して表示が維持されることも確認する。明暗設定と文字サイズを変えたときの本文・操作・システムバーの見やすさは、UI 変更の内容に応じて確認する。
7. 空ファイルでは空であることが表示され、不正な UTF-8 のファイルでは再選択を案内することを確認する。
8. 長いサンプルを端末へ転送し、手動スクロールで末尾の `項目 10000` が読めることを確認する。

```sh
python3 - <<'PY'
from pathlib import Path
Path('/tmp/org-reader-long.org').write_text(
    '* 長い文書\n' + '\n'.join(f'- 項目 {i}' for i in range(1, 10001)),
    encoding='utf-8',
)
PY
adb push /tmp/org-reader-long.org /sdcard/Download/org-reader-long.org
```

Dropbox の経路とは別に表示だけを確認する場合は、`adb push examples/smoke.org /sdcard/Download/org-reader-smoke.org` で転送できる。Dropbox からの保存を省略した場合は、その経路は未確認として記録する。

ADB で転送したファイルが標準選択画面に出ない場合は、転送したファイルを次のようにスキャンし、選択画面のフォルダを開き直す。実機確認ではこの操作後にサンプルを選択できた。

```sh
adb shell content call --uri content://media --method scan_file --arg /sdcard/Download/org-reader-long.org
```

空ファイル・不正 UTF-8 の入力も合成できる。転送後は本アプリの標準選択画面から開き、不正 UTF-8 のエラー後に正常な文書を選び直せることまで確認する。

```sh
python3 - <<'PY'
from pathlib import Path
Path('/tmp/org-reader-empty.org').write_bytes(b'')
Path('/tmp/org-reader-invalid-utf8.org').write_bytes(b'\xff\xfe')
PY
adb push /tmp/org-reader-empty.org /sdcard/Download/org-reader-empty.org
adb push /tmp/org-reader-invalid-utf8.org /sdcard/Download/org-reader-invalid-utf8.org
```

文書の途中へ移動してから回転・取り消しを行い、閲覧位置も維持されることを確認する。公開サンプルのコピーを更新して同じファイルを再選択し、古い表示が置き換わって先頭から読めることも確認する。保存や永続化を追加する変更では、アプリ再起動後の保持を受け入れ条件へ追加する。

## 結果を記録する

確認記録には、日付、APK の取得元と SHA-256、端末と OS、操作、期待結果、実際の結果を残す。ファイルの内容や端末の識別子など、ローカル専用の情報は公開レポートへ含めない。

CI の run・対象コミットと、実行した操作・省略した操作を記載する。ユーザーが確認した結果は、agent による確認と主体を分けて残す。記録先と完了報告の形式は[開発手順](development-workflow.md#6-完了条件と報告)に従う。

確認後は画面点灯・回転・明暗・文字サイズなどを元に戻す。検証用に追加したデータを片付ける場合も対象を限定し、既存の文書は削除しない。
