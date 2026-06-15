# tl-reader-skill

ブルーアーカイブのプレイ動画からEXスキル実行タイムラインを読むための、エージェント向けskill集です。Claude Code と Codex の両方で使うことを想定しています。

このリポジトリには次の2つのskillがあります。

- `yt-dlp`: YouTube、Bilibili、その他 `yt-dlp` 対応サイトの動画をMP4として保存する。
- `tl-reader`: ブルーアーカイブの戦闘動画を保存または再利用し、EXスキル実行候補のレビュー用画像を作り、エージェントがタイムラインを読み取る。

## 使い方

Claude Code では slash command として呼び出します。

```text
/yt-dlp https://www.youtube.com/watch?v=...
/tl-reader https://www.youtube.com/watch?v=...
```

Codex ではリポジトリ共有のskillを `$skill-name` で明示呼び出しします。

```text
$yt-dlp https://www.youtube.com/watch?v=...
$tl-reader https://www.youtube.com/watch?v=...
```

Codex CLI の `/...` は主に組み込みコマンド用です。共有skillを確実に使うには `$yt-dlp` や `$tl-reader` を使ってください。

## ディレクトリ構成

```text
skills/
  yt-dlp/
    SKILL.md
    scripts/download_video.py
    agents/openai.yaml
  tl-reader/
    SKILL.md
    scripts/prepare_timeline.py
    agents/openai.yaml
```

`SKILL.md` はエージェントが読む日本語の作業手順です。`scripts/` 以下には、エージェントが実行する補助スクリプトがあります。

## セットアップ

Python 3 と `ffmpeg` が必要です。`yt-dlp` は未導入でも `yt-dlp` skill のスクリプトがユーザーキャッシュ配下に仮想環境を作り、自動で導入します。

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

Homebrew を使わない macOS では、Python 3 が利用可能なら `yt-dlp` 用の仮想環境はスクリプトが作成します。Deno は公式インストーラでも導入できます。

```bash
curl -fsSL https://deno.land/install.sh | sh
```

YouTube の JavaScript challenge 対応では Deno 2.3.0 以上を推奨します。Node.js 22 以上も使えますが、`yt-dlp` に `--js-runtimes node` を明示する必要があります。

## yt-dlp skill

動画URLをMP4として保存します。保存先を指定しない場合は `~/Downloads/yt-dlp` を使います。

```bash
python3 skills/yt-dlp/scripts/download_video.py "https://www.youtube.com/watch?v=..."
python3 skills/yt-dlp/scripts/download_video.py "https://www.youtube.com/watch?v=..." "~/Downloads/videos"
```

主なオプション:

- `--cookies-from-browser chrome`: ブラウザCookieが必要な動画で使う。
- `--playlist`: プレイリスト全体を保存する。
- `--simulate`: ダウンロードせず、抽出とフォーマット選択だけ確認する。
- `--upgrade`: キャッシュ内の `yt-dlp` を更新する。
- `--extra-arg`: `yt-dlp` に追加引数を渡す。

例:

```bash
python3 skills/yt-dlp/scripts/download_video.py "https://www.youtube.com/watch?v=..." --extra-arg=--js-runtimes --extra-arg=deno
```

## tl-reader skill

ブルーアーカイブの戦闘動画から、次の形式のEXスキル実行タイムラインを作るためのskillです。

```text
7.7 (3:43.500) カヨコ
3.1 (3:42.633) クルミ
```

入力はYouTube/Bilibili等のURL、またはローカルMP4です。URLの場合、MP4が未保存なら `yt-dlp` skill のスクリプトで `~/Downloads/yt-dlp` に保存します。すでに同じ動画IDのMP4がある場合は再利用します。

```bash
python3 skills/tl-reader/scripts/prepare_timeline.py "https://www.youtube.com/watch?v=..."
python3 skills/tl-reader/scripts/prepare_timeline.py "/path/to/video.mp4"
```

生成物は標準では `~/Downloads/tl-reader/<動画名>/` に保存されます。

- `review.md`: エージェントが読むレビュー手順と候補一覧。
- `scan_ui_*.jpg`: カードUIを流し見るためのシート。
- `scan_full_1fps.jpg`: 動画全体を1fpsで俯瞰するシート。
- `candidate_*_ui.jpg`: コスト減少候補のUIクロップ。
- `candidate_*_full.jpg`: コスト減少候補のフルフレーム。
- `candidate_drops.tsv`: 検出されたコスト減少候補。

`tl-reader` は完全自動OCRではありません。スクリプトは候補画像を準備し、エージェントがカード、コストバー、戦闘タイマー、スキル名バナーを目視で確認してタイムラインを作ります。

## 読み取り方の方針

- カード消失だけで判断せず、必ずコスト減少を確認する。
- 戦闘タイマーは右上のゲーム内タイマーを使い、動画再生時刻は出力しない。
- コストは青い箱の満タン数と次箱の塗りから小数1桁で読む。
- 生徒名は選択カードのポートレートと衣装を最優先し、スキル効果テキストだけで決めない。
- カードが浮く、グレーアウトする、`キャンセル` が出る状態は強い証拠だが必須ではない。高速タップでは映らないことがある。
- 高速発動では、コスト減少、カード消失/置換、直後のスキル名バナーまたは固有演出を合わせて判断する。
- 初版では0コスト化された追撃EXや、コスト減少を伴わない発動は除外する。

## 注意

動画の保存や利用は、各サービスの利用規約、著作権、アクセス権を尊重してください。非公開動画、会員限定動画、Cookieが必要な動画を扱う場合は、保存してよい権限があることを確認してください。
