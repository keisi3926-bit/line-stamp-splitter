# LINE Stamp Splitter

AI生成スタンプの一覧画像または複数の元画像を、LINE Creators Market向けの静止画PNGへ分割・整形し、ZIPにまとめるツールです。

## スマホ版

`mobile_pwa/` はiPhone / Android対応のPWAです。画像処理はブラウザ内で完結し、画像をサーバーへ送信しません。

GitHub Pagesを有効にすると、リポジトリのPages URLからそのままGUIを利用できます。

詳しい使い方は [mobile_pwa/README.md](mobile_pwa/README.md) を参照してください。

## Python CLI版

```bash
cd line_stamp_splitter
python -m pip install -r requirements.txt
python line_stamp_splitter.py input.png --rows 4 --cols 4 --count 16 --remove-white-bg --zip
```

詳しい使い方は [line_stamp_splitter/README.md](line_stamp_splitter/README.md) を参照してください。

## 主な機能

- グリッド画像または複数画像から入力
- 8 / 16 / 24 / 32 / 40個の静止画スタンプ
- 白背景除去、余白トリミング、padding
- スタンプ画像を370x320以内の透過PNGへ変換
- main.png、tab.png、report.txt、提出用ZIPを生成

最終提出前にはLINE Creators Marketの最新ガイドラインと生成画像の権利関係を確認してください。
