"""
Gemini APIを使用してPDFファイルのOCR（文字認識）を行い、構造化されたJSONデータを出力するプログラム。
PDFの各ページを抽出し、Geminiに送信してテキストとその位置情報を抽出します。
コマンドラインから実行し、ファイルまたはディレクトリを指定してまとめて処理できます。

Usage:
    python ocr_court_doc.py <PDF_PATH_OR_DIR> [--batch_size <NUMBER>] [--start_page <NUMBER>] [--end_page <NUMBER>]

出力は、各PDFと同じディレクトリに .json 拡張子で保存されます。
"""

import sys
import argparse
from pathlib import Path

try:
    from lib.pdf_processor import pdf_to_text
except ImportError:
    # For when running from a different directory or as a module
    try:
        from .lib.pdf_processor import pdf_to_text
    except ImportError:
        # Fallback if running directly from src
        import sys
        sys.path.append(str(Path(__file__).resolve().parent))
        from lib.pdf_processor import pdf_to_text

if __name__ == "__main__":
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description="Gemini Batch APIを使用してPDFのOCRを行い、構造化JSONを出力します。")
    parser.add_argument("input_path", type=str, help="処理対象のPDFファイルパスまたはディレクトリパス")
    parser.add_argument("--batch_size", type=int, default=1, help="一度に処理するページ数 (デフォルト: 1)")
    parser.add_argument("--start_page", type=int, default=1, help="開始ページ番号 (1開始, デフォルト: 1)")
    parser.add_argument("--end_page", type=int, default=None, help="終了ページ番号 (1開始, デフォルト: 最終ページ)")
    
    args = parser.parse_args()
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
                end_page=args.end_page
            )
    else:
        # 単一ファイルの処理
        pdf_to_text(
            input_path, 
            batch_size=args.batch_size, 
            start_page=args.start_page, 
            end_page=args.end_page
        )
