import sys
import re
import argparse
from pathlib import Path

def merge_ocr_pages(file_path: Path):
    """
    OCRで出力されたMarkdownファイルからページ区切りマーカーを処理（結合・削除）し、
    整形された _clean.md ファイルとして保存する。
    """
    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. 新しいページ区切り形式の処理
        # パターン: =-- End Printed Page ... --= (改行/空白) =-- Begin Page ... --=
        # どちらかに (Continuation) があれば結合する
        
        # 境界マーカーとその前後の空白（改行含む）をマッチさせる
        boundary_pattern = r'\s*(=-- End Printed Page [^\n]*? --=)\s*(=-- Begin Page [^\n]*? --=)\s*'
        
        def replace_boundary(match):
            end_marker = match.group(1)
            begin_marker = match.group(2)
            
            if "(Continuation)" in end_marker or "(Continuation)" in begin_marker:
                # Continuationがある場合は、マーカーとその前後の空白を全て削除（段落結合）
                return ""
            else:
                # Continuationがない場合は、マーカーを削除し、空行(段落区切り)を入れる
                return "\n\n"

        content = re.sub(boundary_pattern, replace_boundary, content, flags=re.DOTALL)

        # 2. 残った単独のマーカー（ファイルの先頭や末尾など）を削除
        content = re.sub(r'=-- Begin Page [^\n]*? --=\s*', '', content)
        content = re.sub(r'\s*=-- End Printed Page [^\n]*? --=', '', content)

        # 3. 旧形式のマーカー処理（念のため残しておく）
        cont_pattern = r'\s*^=-- Page .*?\(Continuation\).*?--=\s*'
        content = re.sub(cont_pattern, '', content, flags=re.MULTILINE)
        normal_pattern = r'^=-- Page .*?--=\s*\n?'
        content = re.sub(normal_pattern, '', content, flags=re.MULTILINE)
        
        new_content = content
        
        # 3つ以上の連続する改行を2つ（1つの空行）に置換して整える
        new_content = re.sub(r'\n{3,}', '\n\n', new_content)
        
        # 出力ファイル名 (例: file_paged.md -> file.md)
        if file_path.name.endswith("_paged.md"):
            output_path = file_path.with_name(file_path.name.replace("_paged.md", ".md"))
        else:
            output_path = file_path.with_name(file_path.stem + "_merged" + file_path.suffix)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"[SUCCESS] Created: {output_path}")

    except Exception as e:
        print(f"[ERROR] Failed to process {file_path}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCRで出力されたMarkdownのページ区切りを処理し、テキストを結合・整形します。")
    parser.add_argument("input_path", type=str, help="対象のMarkdownファイルまたはディレクトリ")
    
    args = parser.parse_args()
    input_path = Path(args.input_path)
    
    if input_path.is_dir():
        md_files = list(input_path.glob("*_paged.md"))
        if not md_files:
            # _paged.md が見つからない場合は全ての .md を対象にする
            md_files = list(input_path.glob("*.md"))
            
        print(f"[INFO] Found {len(md_files)} Markdown files in {input_path}")
        for md_file in md_files:
            # 既に処理済みのファイルや、意図しないファイルを除外
            if md_file.name.endswith("_merged.md") or md_file.name.endswith("_clean.md"):
                continue
            merge_ocr_pages(md_file)
    else:
        merge_ocr_pages(input_path)
