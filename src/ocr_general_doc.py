"""
Gemini APIを使用してPDFファイルのOCR（文字認識）を行い、Markdownデータを出力するプログラム。
一般文書（証拠書類、書籍など）を対象としています。
PDFの各ページを抽出し、Geminiに送信してテキストを抽出します。
コマンドラインから実行し、ファイルまたはディレクトリを指定してまとめて処理できます。

Usage:
    python ocr_general_doc.py <PDF_PATH_OR_DIR> [--batch_size <NUMBER>] [--start_page <NUMBER>] [--end_page <NUMBER>]

出力は、各PDFと同じディレクトリに .md 拡張子で保存されます。
"""

import sys
import argparse
from pathlib import Path

try:
    from lib.pdf_to_markdown import pdf_to_text, get_ocr_prompt
except ImportError:
    # For when running from a different directory or as a module
    try:
        from .lib.pdf_to_markdown import pdf_to_text, get_ocr_prompt
    except ImportError:
        # Fallback if running directly from src
        import sys
        sys.path.append(str(Path(__file__).resolve().parent))
        from lib.pdf_to_markdown import pdf_to_text, get_ocr_prompt

# 一般文書のスタイル定義
GENERAL_DOC_STYLE = """
# CONTEXT: General Document (Evidence, Books, Reports, etc.)
- **Format**: Maintain the original structure as much as possible.
- **Line Breaks**: Merge lines within the same paragraph. Keep line breaks for headings, lists, and clear paragraph transitions.
- **Tables**: If tables are present, represent them using Markdown table format.
- **Lists**: Use standard Markdown list markers (`-`, `*`, or `1.`).
- **Exclusions**: Ignore headers, footers, and page numbers if they are repetitive and not part of the main content.
- **Page Numbers**: Page numbers may be Arabic (1, 2), Kanji (一, 二), or Roman (I, II) numerals. Omit them if they are in margins, but use them for the Page Markers (converting to Arabic numerals).
- **Emphasis**: Use bold (`**text**`) or italics (`*text*`) where appropriate based on the visual style of the document.
"""

if __name__ == "__main__":
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description="Gemini Batch APIを使用して一般文書のPDFのOCRを行い、Markdownを出力します。")
    parser.add_argument("input_path", type=str, nargs='?', help="処理対象のPDFファイルパスまたはディレクトリパス")
    parser.add_argument("--batch_size", type=int, default=4, help="一度に処理するページ数 (デフォルト: 4)")
    parser.add_argument("--start_page", type=int, default=1, help="開始ページ番号 (1開始, デフォルト: 1)")
    parser.add_argument("--end_page", type=int, default=None, help="終了ページ番号 (1開始, デフォルト: 最終ページ)")
    parser.add_argument("--show_prompt", action="store_true", help="実行せずにプロンプトのみを表示します。")
    
    args = parser.parse_args()

    if args.show_prompt:
        print("\n--- Gemini OCR Prompt Template ---")
        print(get_ocr_prompt(args.batch_size, GENERAL_DOC_STYLE))
        print("----------------------------------\n")
        sys.exit(0)

    if not args.input_path:
        parser.error("the following arguments are required: input_path (unless --show_prompt is used)")

    input_path = Path(args.input_path)
    
    if input_path.is_dir():
        # ディレクトリ内の全てのPDFファイルを対象にする（ファイル名順にソート）
        pdf_files = sorted(list(input_path.glob("*.pdf")), key=lambda x: x.name)
        if not pdf_files:
            print(f"[WARN] No PDF files found in directory: {input_path}")
            sys.exit(0)
        
        print(f"[INFO] Found {len(pdf_files)} PDF files in {input_path}")
        for pdf_file in pdf_files:
            print(f"\n[PROCESS] Starting: {pdf_file.name}")
            pdf_to_text(
                pdf_file, 
                batch_size=args.batch_size, 
                start_page=args.start_page, 
                end_page=args.end_page,
                context_instruction=GENERAL_DOC_STYLE
            )
    else:
        # 単一ファイルの処理
        pdf_to_text(
            input_path, 
            batch_size=args.batch_size, 
            start_page=args.start_page, 
            end_page=args.end_page,
            context_instruction=GENERAL_DOC_STYLE
        )
