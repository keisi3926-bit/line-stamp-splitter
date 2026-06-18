# LINE Creators Market AI Stamp Splitter

ChatGPTなどで生成した1枚のスタンプ一覧画像、または複数の元画像を、LINE Creators Marketへ提出しやすい静止画スタンプ用PNGとZIPに整形するPython CLIツールです。

アニメーション、絵文字、着せかえには対応していません。

## インストール

Python 3.10以上を用意し、依存ライブラリをインストールします。

```bash
cd line_stamp_splitter
python -m pip install -r requirements.txt
```

## 基本仕様

- スタンプ数は 8 / 16 / 24 / 32 / 40 に対応
- スタンプ画像はPNG、最大 370x320 px
- `main.png` は 240x240 px
- `tab.png` は 96x74 px
- 透明PNGとして保存
- 縦横サイズは偶数pxへ調整
- PNG最適化を行い、1MB超過時はレポートに警告
- 白背景除去は `--remove-white-bg` 指定時のみ実行

## グリッド画像から作る例

```bash
python line_stamp_splitter.py input.png --rows 4 --cols 4 --count 16 --zip
```

白背景を透明化したい場合:

```bash
python line_stamp_splitter.py input.png --rows 4 --cols 4 --count 16 --remove-white-bg --white-threshold 245 --zip
```

## フォルダ画像から作る例

```bash
python line_stamp_splitter.py ./input_images --count 16 --zip
```

余白を増やす場合:

```bash
python line_stamp_splitter.py ./input_images --count 16 --padding 20 --zip
```

`main.png` と `tab.png` の元画像を3番目のスタンプにする場合:

```bash
python line_stamp_splitter.py ./input_images --count 16 --main-index 3 --tab-index 3 --zip
```

## 出力

デフォルトでは `output_line_stickers/` に出力します。

```text
output_line_stickers/
  main.png
  tab.png
  01.png
  02.png
  ...
  line_stickers.zip
  report.txt
```

出力先を変える場合:

```bash
python line_stamp_splitter.py input.png --rows 4 --cols 4 --count 16 --output my_stickers --zip
```

既存出力を上書きする場合は `--overwrite` を付けてください。

## テスト用ダミー画像

フォルダ入力用:

```bash
python create_dummy_images.py --output dummy_input --count 16
python line_stamp_splitter.py dummy_input --count 16 --remove-white-bg --zip
```

グリッド入力用:

```bash
python create_dummy_images.py --grid --output dummy_grid.png --rows 4 --cols 4 --count 16
python line_stamp_splitter.py dummy_grid.png --rows 4 --cols 4 --count 16 --remove-white-bg --zip
```

## LINE提出前の注意

このツールはLINE Creators Marketの一般的な静止画仕様に合わせて整形と検証を行いますが、最終提出前にはLINE Creators Marketの管理画面で表示、透過、余白、ファイルサイズ、審査ガイドラインを必ず確認してください。

特にAI生成画像は、文字の崩れ、透過漏れ、白フチ、権利侵害に見える要素がないかを人の目で確認することをおすすめします。

## 既知の制限

- グリッド切り出しは等間隔セルを前提にしています。
- 複雑な白背景や淡い白色のイラストは、`--remove-white-bg` で一部が透明化される可能性があります。
- 1MB超過時はPNG最適化と段階的縮小を試しますが、完全な保証はしません。
- アニメーションスタンプ、絵文字、着せかえには未対応です。
