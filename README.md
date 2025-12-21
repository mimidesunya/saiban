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

### Copper PDF ドライバのインストール

以下のコマンドを実行して、Copper PDFのPythonドライバを自動的にダウンロード・インストールします。

```bash
python setup.py
```

このスクリプトは、ドライバをダウンロードし、現在のPython環境にインストールします。

### PDFの生成

#### 1. ドラッグ＆ドロップで変換
`bin/generate_court_pdf.bat` に、変換したいテキストファイルまたはHTMLファイルをドラッグ＆ドロップしてください。

#### 2. クリップボードから変換 / AI生成
`bin/generate_court_pdf.bat` をダブルクリックして実行すると、インタラクティブモードが起動します。
クリップボードにコピーされたテキストを元に、AI (Gemini) を使用して裁判書面形式のHTMLを生成し、PDFに変換します。
※ AI機能を使用するには `ai_config.json` の設定が必要です。

#### 3. コマンドラインから実行
```bash
python src/generate_court_doc.py [入力ファイルパス]
```

生成されたPDFは `output/` フォルダに保存されます。
ファイル名は、文書内のタイトルと日付に基づいて自動生成されます（例: `2025-12-21-準備書面.pdf`）。

なお、変換には公開サーバー `ctip://cti.li/` を使用しています。

### PDF OCR (文字認識)

PDFファイルや画像ファイルをテキスト化（Markdown形式）したい場合は、以下の手順で行います。

#### 1. ドラッグ＆ドロップでOCR
`bin/ocr_court_doc.bat` に、OCRをかけたいPDFファイルまたはフォルダをドラッグ＆ドロップしてください。
Gemini APIを使用して文字認識を行い、同じフォルダにJSONファイルとMarkdownファイルを出力します。

## AI設定 (Gemini)

AIによる文書生成機能を使用する場合は、`ai_config.template.json` を `ai_config.json` にリネームし、Google Gemini APIキーを設定してください。

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
│   ├── generate_court_doc.py   # 裁判文書生成メインスクリプト
│   ├── instructions/           # AIへの指示書
│   │   └── ai_instruction.md
│   ├── lib/                    # ライブラリ
│   │   └── pdf_converter.py    # PDF変換ロジック
│   └── template/               # HTML/CSSテンプレート
│       ├── text.html           # サンプルHTML
│       └── style.css           # 裁判書面用CSS (CSS 2.1準拠)
├── output/                     # 生成されたPDFの出力先
├── ai_config.json              # AI設定ファイル (要作成)
├── bin/
│   ├── generate_court_pdf.bat  # 裁判文書生成用バッチ
│   └── ocr_court_doc.bat       # OCR用バッチ
├── setup.py                    # ドライバセットアップスクリプト
└── README.md                   # 本ファイル
```

## 前提条件

1.  Python 3.x がインストールされていること。
2.  インターネット接続があること（公開サーバー `cti.li` を使用するため）。

## 今後の予定

*   基本的な書面（訴状など）のHTMLテンプレート作成
*   縦書き・横書き対応のCSS設計
*   Pythonによるデータ挿入とPDF変換スクリプトの実装
