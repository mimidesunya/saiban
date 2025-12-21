
def json_to_markdown(pages_data: list[dict]) -> str:
    """
    OCR結果のJSONデータをMarkdown形式に変換する。
    """
    md_lines = []
    
    def append_block(label, text):
        if not text:
            return
        if label == "title":
            md_lines.append(f"# {text}")
        elif label == "sectionHeading":
            md_lines.append(f"## {text}")
        elif label == "subHeading":
            md_lines.append(f"### {text}")
        elif label == "caption":
            md_lines.append(f"> {text}")
        elif label in ["isolated", "ignored"]:
            return
        elif label in ["header", "footer", "pageNumber"]:
            md_lines.append(f"*{text}*")
        else: # body
            md_lines.append(text)
        md_lines.append("")

    for page in pages_data:
        page_num = page.get("page_number", "?")
        md_lines.append(f"## Page {page_num}")
        md_lines.append("")
        
        buffer_text = ""
        buffer_label = None
        
        for block in page.get("blocks", []):
            text = block.get("text", "")
            # 空白のみの場合はスキップするが、改行コードが含まれる場合は保持したいので注意が必要
            # ただし、通常は意味のあるテキストが含まれるはず
            if not text.strip():
                continue
                
            label = block.get("label", "body")
            continues = block.get("continues", False)
            
            # ラベルが変わったら強制フラッシュ
            if buffer_label is not None and label != buffer_label:
                append_block(buffer_label, buffer_text)
                buffer_text = ""
            
            buffer_label = label
            buffer_text += text
            
            # continuesがFalseなら区切り
            if not continues:
                append_block(buffer_label, buffer_text)
                buffer_text = ""
                buffer_label = None
        
        # ページの最後でバッファが残っていれば出力
        if buffer_text and buffer_label:
            append_block(buffer_label, buffer_text)
        
        md_lines.append("---") # ページ間に区切り線
        md_lines.append("")
        
    return "\n".join(md_lines)
