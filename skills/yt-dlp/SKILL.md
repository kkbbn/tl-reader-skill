---
name: yt-dlp
description: YouTube、Bilibili、その他 yt-dlp 対応サイトの動画URLをMP4としてダウンロードする。ユーザーが動画リンクを保存したい、保存先ディレクトリを指定したい、yt-dlpのセットアップも含めて実行したい場合に使う。
---

# yt-dlp

## 目的

YouTube、Bilibili、その他 `yt-dlp` が対応するサイトの動画URLを、MP4ファイルとしてローカルに保存する。保存先が指定されていない場合は `~/Downloads/yt-dlp` を使う。

著作権、利用規約、アクセス権を尊重し、ユーザーが保存してよい動画だけを扱う。

## 呼び出し方

- Claude Code: `/yt-dlp <URL> [保存先ディレクトリ]`
- Codex: `$yt-dlp <URL> [保存先ディレクトリ]` または `/skills` から選択する

Codex CLI の `/...` は主に組み込みコマンド用で、リポジトリ共有の skill は `$yt-dlp` として明示呼び出しする。

## 実行手順

1. ユーザー入力から動画URLを1つ取り出す。保存先ディレクトリが明示されていなければ `~/Downloads/yt-dlp` を使う。
2. リポジトリルートから次を実行する。

```bash
python3 skills/yt-dlp/scripts/download_video.py "<URL>"
python3 skills/yt-dlp/scripts/download_video.py "<URL>" "<保存先ディレクトリ>"
```

3. `yt-dlp` が未導入なら、スクリプトがユーザーキャッシュ配下に仮想環境を作成して `yt-dlp` を導入する。システムに `yt-dlp` がある場合はそれを優先する。
4. ダウンロード結果の保存先、実行時の警告、失敗理由をユーザーに簡潔に伝える。

## オプション

- ブラウザのCookieが必要な動画では、ユーザーの許可を得て `--cookies-from-browser` を使う。

```bash
python3 skills/yt-dlp/scripts/download_video.py "<URL>" --cookies-from-browser chrome
```

- YouTubeでJavaScriptランタイムを明示する必要がある場合は `--extra-arg=--js-runtimes --extra-arg=deno` を使う。Denoが `PATH` にない場合は `--extra-arg=--js-runtimes --extra-arg=deno:/path/to/deno` のように指定する。

```bash
python3 skills/yt-dlp/scripts/download_video.py "<URL>" --extra-arg=--js-runtimes --extra-arg=deno
```

- プレイリスト全体を保存する必要がある場合だけ `--playlist` を使う。通常は単一動画として扱う。

```bash
python3 skills/yt-dlp/scripts/download_video.py "<URL>" "<保存先ディレクトリ>" --playlist
```

- ダウンロードせずに抽出とフォーマット選択だけ確認する場合は `--simulate` を使う。

```bash
python3 skills/yt-dlp/scripts/download_video.py "<URL>" --simulate
```

- サイト側変更で失敗する場合は `--upgrade` でキャッシュ内の `yt-dlp` を更新してから再実行する。

```bash
python3 skills/yt-dlp/scripts/download_video.py "<URL>" --upgrade
```

## 依存関係の扱い

スクリプトは `yt-dlp[default]` を自動セットアップする。`yt-dlp[default]` にはYouTubeのJavaScript challenge solverで使う `yt-dlp-ejs` が含まれる。

高品質なMP4結合や変換には `ffmpeg` が必要になる。`ffmpeg` がない場合はスクリプトが単一MP4形式を優先して試すが、動画サイトによっては品質が落ちる、または失敗する。

YouTubeでは外部JavaScriptランタイムが必要になることがある。推奨はDeno 2.3.0以上。yt-dlpではDenoが推奨かつデフォルト有効で、権限制限つきで実行される。Node.js 22以上も利用できるが `--js-runtimes node` の明示が必要。QuickJS / QuickJS-NGは軽量だが、古い版では非常に遅くなる場合がある。Bunはyt-dlp側で非推奨扱いなので新規導入しない。

Ubuntu / WSL2:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip ffmpeg
curl -fsSL https://deno.land/install.sh | sh
export PATH="$HOME/.deno/bin:$PATH"
deno --version
```

macOS:

```bash
brew install yt-dlp ffmpeg deno
```

Homebrew を使わないmacOSでは、Python 3 が利用可能ならスクリプトが `yt-dlp` 用の仮想環境を作る。Denoは公式インストーラで導入できる。

```bash
curl -fsSL https://deno.land/install.sh | sh
```

`ffmpeg` は利用者が信頼する配布元またはパッケージ管理ツールで導入する。
