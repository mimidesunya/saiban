# 日本の裁判書面作成プロジェクト (CSS 2.1 + Copper PDF)

このプロジェクトは、日本の裁判所で使用される書面（訴状、準備書面など）を、HTMLとCSS 2.1準拠のCSSを用いて作成し、Copper PDFを使用してPDF化する試みです。

## 概要

日本の裁判書面は、A4縦書き、横書き、行数、文字数、余白などの厳格なフォーマットが求められることがあります。
本プロジェクトでは、Web技術（HTML/CSS）を用いてこれらのレイアウトを制御し、Pythonスクリプトを通じてデータを流し込み、印刷可能なPDFを生成することを目指します。

## 技術スタック

*   **言語**: Python
*   **マークアップ**: HTML5
*   **スタイル**: CSS 2.1 (Copper PDFがサポートする範囲)
*   **PDFレンダリング**: [Copper PDF](https://copper-pdf.com/) (CTI)

## セットアップ

### 初期設定

以下のコマンドを実行して、Copper PDFドライバのインストールと、AI指示書の生成を行います。

```bash
python setup.py
```

*   **ドライバ**: Copper PDFのPythonドライバが未インストールの場合は自動的にインストールされます。
*   **AI指示書**: `src/templates` 内のHTMLテンプレートと `src/base/ai_instruction.md` を結合し、`instructions/` フォルダに個別の指示書（Markdown）を生成します。

## 機能と使い方 (binフォルダ内のバッチファイル)

`bin` フォルダ内のバッチファイルを使用して各機能を実行できます。

### 1. 裁判資料PDF作成 (`bin/裁判資料PDF作成.bat`)
テキストファイルやHTMLファイルをドラッグ＆ドロップすると、PDFに変換します。
ダブルクリックして実行すると、クリップボードのテキストを元にAI (Gemini) がHTMLを生成し、PDF化します。
※ AI機能を使用するには `ai_config.json` の設定が必要です。

### 2. 文書OCR (`bin/文書OCR.bat`)
PDFファイルや画像フォルダをドラッグ＆ドロップすると、Gemini APIを使用して高精度なOCRを行います。
結果はMarkdown形式で保存されます。

### 3. ページ区切り除去 (`bin/ページ区切り除去.bat`)
OCRで生成されたMarkdownファイルをドラッグ＆ドロップすると、ページ区切り（`=-- Begin Page...`）を除去し、段落を適切に結合して整形します。

### 4. テンプレートプレビュー (`bin/テンプレートプレビュー.bat`)
基本テンプレート（`src/base/text.html`）をPDFに変換してプレビュー表示します。
スタイルの調整確認に使用します。

## AI設定 (Gemini)

AI機能を使用する場合は、`ai_config.template.json` を `ai_config.json` にリネームし、Google Gemini APIキーを設定してください。

```json
{
    "gemini": {
        "apiKey": "YOUR_API_KEY_HERE",
        "textModel": "gemini-pro"
    }
}
```

## フォルダ構成

```
.
├── src/
│   ├── base/                   # 基本テンプレート (text.html, style.css) と AI指示書ひな形 (ai_instruction.md)
│   ├── templates/              # 各種書面テンプレート (控訴状.htmlなど)
│   ├── lib/                    # ライブラリ
│   ├── generate_court_doc.py   # 文書生成スクリプト
│   ├── ocr_court_doc.py        # 裁判文書OCRスクリプト
│   ├── ocr_general_doc.py      # 一般文書OCRスクリプト
│   ├── ocr_merge_pages.py      # OCRページ結合スクリプト
│   └── preview_template.py     # プレビュースクリプト
├── instructions/               # 生成されたAI指示書 (setup.pyで生成)
├── output/                     # 生成されたPDFの出力先
├── bin/                        # 実行用バッチファイル群
│   ├── 裁判文書PDF作成.bat
│   ├── 裁判文書OCR.bat         # 裁判文書用OCR
│   ├── 一般文書OCR.bat         # 一般文書用OCR
│   ├── OCRページ結合.bat       # OCR後のページ結合・整形
│   └── テンプレートプレビュー.bat
├── ai_config.json              # AI設定ファイル
├── setup.py                    # セットアップ＆指示書生成スクリプト
└── README.md                   # 本ファイル
```

## 前提条件

1.  Python 3.x がインストールされていること。
2.  インターネット接続があること（公開サーバー `cti.li` を使用するため）。
