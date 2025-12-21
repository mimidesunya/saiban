import sys
import time
import json
import base64
from pathlib import Path
import fitz  # PyMuPDF: PDFの操作と画像化に使用
from google.genai import types

try:
    from . import gemini_client
except ImportError:
    import gemini_client

try:
    from .json_to_md import json_to_markdown
except ImportError:
    import json_to_md

# 1. Gemini APIクライアントの初期化
client = gemini_client.get_gemini_client()

# 使用するGeminiモデルのID (Batch API対応モデル)
# 明示的に gemini-3-flash-preview を指定
MODEL_ID = "gemini-3-flash-preview"

# エラー時のリトライ設定
MAX_RETRIES = gemini_client.MAX_RETRIES
INITIAL_RETRY_DELAY = gemini_client.INITIAL_RETRY_DELAY

def validate_ocr_result(data: any, expected_pages: int) -> tuple[bool, str]:
    """
    OCR結果のJSONデータが正しい形式かどうかを検証する。
    """
    if not isinstance(data, list):
        # 単一オブジェクトの場合はリストにラップしてチェック
        if isinstance(data, dict) and "blocks" in data:
            data = [data]
        else:
            return False, "Response is not a list or a valid page object"
            
    if len(data) != expected_pages:
        return False, f"Page count mismatch: expected {expected_pages}, got {len(data)}"
        
    # ページ番号のチェック (1から始まる連番であることを期待)
    page_nums = sorted([item.get("page_number", 0) for item in data])
    expected_nums = list(range(1, expected_pages + 1))
    
    if page_nums != expected_nums:
        return False, f"Invalid page numbers: expected {expected_nums}, got {page_nums}"
        
    return True, ""

def run_batch_api_ocr(batch_tasks: list, generation_config: types.GenerateContentConfig) -> list[dict]:
    """
    Gemini Batch APIを使用して複数のリクエストを一括処理する。
    20MBの制限を考慮し、必要に応じて複数のバッチジョブに分割して実行する。
    バリデーションとリトライ機能付き。
    
    Args:
        batch_tasks: List of (page_mapping, pdf_bytes) tuples.
                     page_mapping is a list of original page numbers (1-based).
    """
    all_results = []
    
    # (page_mapping, pdf_bytes, retry_count)
    pending_tasks = [(t[0], t[1], 0) for t in batch_tasks]
    
    while pending_tasks:
        # 1. Create jobs from pending tasks
        current_batch_requests = []
        current_batch_tasks = [] 
        current_batch_size = 0
        MAX_INLINE_SIZE = 18 * 1024 * 1024 # 安全のため18MBに設定
        
        jobs_to_submit = [] # List of (requests, tasks_in_job)
        
        tasks_to_process = pending_tasks
        pending_tasks = [] # Clear for next iteration
        
        for page_mapping, b_bytes, retry_count in tasks_to_process:
            # AIには常に1ページ目からの相対的な番号で処理させる
            num_pages = len(page_mapping)
            prompt = f"""
# ROLE / SYSTEM
You are a high-precision OCR + document layout extraction engine.
Your output will be parsed by a strict JSON parser and then used to embed an invisible text layer into a PDF.
Therefore: OUTPUT JSON ONLY. No markdown. No code fences. No commentary.

# INPUT
A Japanese document consisting of pages 1..{num_pages}. Each page is provided as an image.

# ABSOLUTE OUTPUT RULES (must follow)
- Return ONLY a single JSON value: an array of page objects.
- Do NOT output any extra text before/after JSON.
- Use valid JSON:
  - Double quotes only
  - No trailing commas
  - Escape special characters inside strings
  - If you need line breaks in text, use the escape sequence \\n (do NOT insert literal newlines inside JSON strings)

# TASK
For every page from 1 to {num_pages}, extract text + layout into structured data.

## 1) Text transcription (accuracy first)
- Transcribe exactly what is written (Japanese).
- Do not translate, summarize, paraphrase, or add missing content.
- Correct ONLY obvious OCR confusions (e.g., 0/O, 1/I, etc.) when clearly supported by context.
- If a character is unreadable, DO NOT guess: use "□" as a placeholder and keep the rest.
- Normalize layout-expanded spacing used for visual design:
  - Example: "領　収　書" -> "領収書"
  - Remove excessive inter-character spaces that are clearly for alignment, not semantic separation.
- Preserve punctuation (。、・「」() etc.) and keep it at the end of the correct block.

## 2) Block segmentation (for PDF text-layer compatibility)
- Default unit = one physical text line (1行) per block whenever possible.
- Split blocks when:
  - direction changes (horizontal vs vertical)
  - font size changes significantly
  - the text belongs to a different logical region (header/footer/page number/caption/title)
- Merge lines ONLY when the page truly contains a single large heading rendered across fragments.

## 3) Bounding boxes (normalized coordinates)
- Use a normalized coordinate system per page:
  - top-left is (0, 0)
  - page width = 1000, page height = 1000
- For each block, output an axis-aligned rectangle:
  - box.x, box.y, box.width, box.height
- Coordinates must be integers in [0, 1000]. Round to nearest integer and clip to range.
- Boxes should tightly enclose the visible glyphs of that block (not the whole column).

## 4) Writing direction
- direction = "horizontal" (default) or "vertical".
- If text is vertical Japanese, set "vertical".
- If mixed within a page, set per block accordingly.

## 5) Logical role labeling
Pick exactly one label for each block:
- title
- sectionHeading
- subHeading
- body
- caption
- footer
- header
- pageNumber
- isolated
- ignored

Labeling heuristics:
- title/sectionHeading/subHeading: larger font and/or prominent placement.
- header: repeated top-of-page items (date, document name, running header).
- footer: bottom notes, legal lines, references.
- pageNumber: page number printed on the page (not the page_number field).
- isolated: content that is semantically isolated from the main flow, such as side notes, column break text, or independent text boxes.
- ignored: content that should be ignored, such as random characters, noise, or irrelevant markings.

## 6) Font size estimation
- font_size is an integer representing relative font size on a 0..1000 page height scale.
- A good approximation is the typical glyph height / line height of the block in the same coordinate system.

## 7) Continuity / paragraph structure
- continues = true if the NEXT block continues the same logical flow (same article/section),
  even if it is a new paragraph inside that same flow.
- Set continues = false ONLY when context clearly breaks (end of article/box, unrelated sidebar, independent caption, page header/footer break, etc.)
- Paragraph breaks INSIDE a continuing flow:
  - Keep continues = true
  - Append "\\n\\n" at the end of the block text that ends a paragraph.

## 8) Reading order inside each page
- Sort blocks in human reading order.
- Horizontal pages: generally top-to-bottom; for multi-column, finish left column before moving to right (unless the layout clearly indicates otherwise).
- Vertical pages: generally right-to-left columns, top-to-bottom within each column.

# OUTPUT FORMAT (JSON)
Return an array with exactly {num_pages} page objects.
If a page has no text, still return: {{ "page_number": N, "blocks": [] }}

Schema example:
[
  {{
    "page_number": 1,
    "blocks": [
      {{
        "text": "抽出されたテキスト",
        "label": "body",
        "font_size": 12,
        "continues": false,
        "direction": "horizontal",
        "box": {{ "x": 100, "y": 200, "width": 300, "height": 50 }}
      }}
    ]
  }}
]
"""
            # PDFデータをBase64エンコード
            b64_data = base64.b64encode(b_bytes).decode('utf-8')
            
            pdf_part = {
                "role": "user",
                "parts": [
                    {"inline_data": {"data": b64_data, "mime_type": "application/pdf"}},
                    {"text": prompt}
                ]
            }
            
            # おおよそのサイズ計算（Base64エンコード後のサイズ）
            req_size = len(b64_data) + len(prompt)
            
            if current_batch_size + req_size > MAX_INLINE_SIZE and current_batch_requests:
                jobs_to_submit.append((current_batch_requests, current_batch_tasks))
                current_batch_requests = []
                current_batch_tasks = []
                current_batch_size = 0
                
            current_batch_requests.append({
                "contents": [pdf_part],
                "config": generation_config
            })
            current_batch_tasks.append((page_mapping, b_bytes, retry_count))
            current_batch_size += req_size
            
        if current_batch_requests:
            jobs_to_submit.append((current_batch_requests, current_batch_tasks))
            
        print(f"[INFO] Submitting {len(jobs_to_submit)} Batch API jobs (Total {len(tasks_to_process)} requests)...")
        
        active_jobs = []
        for i, (job_requests, tasks) in enumerate(jobs_to_submit):
            print(f"[INFO] Creating Batch Job {i+1}/{len(jobs_to_submit)} with {len(job_requests)} requests...")
            try:
                batch_job = client.batches.create(
                    model=MODEL_ID,
                    src=job_requests,
                    config=types.CreateBatchJobConfig(display_name=f"ocr_batch_{i}_{int(time.time())}")
                )
                active_jobs.append((batch_job, tasks))
            except Exception as e:
                print(f"[ERROR] Failed to create batch job: {e}")
                # Job creation failed, retry all tasks in this job
                for t in tasks:
                    if t[2] < MAX_RETRIES:
                        pending_tasks.append((t[0], t[1], t[2] + 1))
                    else:
                        print(f"[ERROR] Max retries reached for task pages {t[0]}")
        
        # 2. ポーリング（完了待ち）
        if not active_jobs:
            if pending_tasks:
                 time.sleep(INITIAL_RETRY_DELAY)
            continue

        print(f"[INFO] Waiting for {len(active_jobs)} jobs to complete...")
        completed_jobs = [False] * len(active_jobs)
        start_time = time.time()
        
        while not all(completed_jobs):
            elapsed = time.time() - start_time
            for i, (job, tasks) in enumerate(active_jobs):
                if completed_jobs[i]:
                    continue
                    
                try:
                    updated_job = client.batches.get(name=job.name)
                except Exception as e:
                    print(f"[WARN] Failed to get job status: {e}")
                    time.sleep(5)
                    continue

                if updated_job.done:
                    job_elapsed = time.time() - start_time
                    print(f"[OK] Job {i+1} finished with state: {updated_job.state} (Elapsed: {job_elapsed:.1f}s)")
                    
                    if updated_job.state == 'JOB_STATE_SUCCEEDED':
                        # 結果の回収
                        if updated_job.dest and updated_job.dest.inlined_responses:
                            responses = updated_job.dest.inlined_responses
                            
                            for res_idx, res in enumerate(responses):
                                task = tasks[res_idx]
                                page_mapping, b_bytes, retry_count = task
                                success = False
                                
                                if res.response and res.response.text:
                                    try:
                                        data = json.loads(res.response.text)
                                        
                                        # Validation
                                        is_valid, error_msg = validate_ocr_result(data, len(page_mapping))
                                        
                                        if is_valid:
                                            if not isinstance(data, list):
                                                data = [data]
                                            
                                            # Fix page numbers
                                            for item in data:
                                                rel_page = item.get("page_number", 1)
                                                if 1 <= rel_page <= len(page_mapping):
                                                    item["page_number"] = page_mapping[rel_page - 1]
                                            
                                            all_results.extend(data)
                                            success = True
                                        else:
                                            print(f"[WARN] Validation failed for pages {page_mapping}: {error_msg}")
                                            
                                    except json.JSONDecodeError as e:
                                        print(f"[WARN] JSON parse error for pages {page_mapping}: {e}")
                                else:
                                    print(f"[WARN] Empty response for pages {page_mapping}")

                                if not success:
                                    if retry_count < MAX_RETRIES:
                                        print(f"[INFO] Retrying pages {page_mapping} (Attempt {retry_count + 2}/{MAX_RETRIES + 1})")
                                        pending_tasks.append((page_mapping, b_bytes, retry_count + 1))
                                    else:
                                        print(f"[ERROR] Max retries reached for pages {page_mapping}")

                        elif updated_job.dest and updated_job.dest.file_name:
                            # JSONLファイルとして出力された場合
                            print(f"[INFO] Results stored in file: {updated_job.dest.file_name}. Downloading...")
                            # ここでは簡易化のため、ファイルダウンロード処理は省略（必要に応じて実装）
                            # 実際には client.files.download を使用
                            pass
                    else:
                        print(f"[ERROR] Job {i+1} failed: {updated_job.error}")
                        # Retry all tasks
                        for t in tasks:
                            if t[2] < MAX_RETRIES:
                                pending_tasks.append((t[0], t[1], t[2] + 1))
                            else:
                                print(f"[ERROR] Max retries reached for task pages {t[0]}")
                    
                    completed_jobs[i] = True
            
            if not all(completed_jobs):
                time.sleep(10) # Polling interval
            
        if pending_tasks:
            print(f"[INFO] {len(pending_tasks)} tasks scheduled for retry. Waiting {INITIAL_RETRY_DELAY}s...")
            time.sleep(INITIAL_RETRY_DELAY)
            
    return all_results

def pdf_to_text(pdf_path: Path, batch_size: int = 5, start_page: int = 1, end_page: int | None = None) -> None:
    """
    PDFファイルを読み込み、各ページを抽出してGemini Batch APIでOCRを実行し、結果をJSONファイルに保存する。
    
    Args:
        pdf_path (Path): 処理対象のPDFファイルパス
        batch_size (int): 一度に処理するページ数
        start_page (int): 開始ページ番号（1開始）
        end_page (int | None): 終了ページ番号（1開始）。Noneの場合は最終ページまで。
    """
    if not pdf_path.exists():
        print(f"[ERROR] PDF file not found: {pdf_path}")
        return

    # 出力先はPDFと同じ場所で拡張子を.jsonに変更
    output_json_path = pdf_path.with_suffix(".json")
    output_md_path = pdf_path.with_suffix(".md")
    
    existing_data = []
    existing_page_nums = set()
    
    if output_json_path.exists():
        try:
            with open(output_json_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                existing_page_nums = {item.get("page_number") for item in existing_data if item.get("page_number")}
            print(f"[INFO] Loaded existing JSON with {len(existing_page_nums)} pages.")
        except Exception as e:
            print(f"[WARN] Failed to load existing JSON: {e}. Starting fresh.")
            existing_data = []
            existing_page_nums = set()

    print(f"[INFO] Opening PDF: {pdf_path}")
    script_start_time = time.time()
    
    try:
        # PDFファイルをオープン
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[ERROR] Failed to open PDF: {e}")
        return

    try:
        total_pages = len(doc)
        # 1-basedから0-basedのインデックスに変換
        s_idx = max(0, start_page - 1)
        e_idx = min(total_pages - 1, (end_page - 1) if end_page is not None else total_pages - 1)

        if s_idx > e_idx:
            print(f"[ERROR] Invalid page range: {start_page} to {end_page} (Total pages: {total_pages})")
            return

        # 処理対象のページ番号（1-based）のリストを作成
        target_pages = list(range(s_idx + 1, e_idx + 2))
        
        # 既に存在するページを除外
        pages_to_process = sorted([p for p in target_pages if p not in existing_page_nums])
        
        if not pages_to_process:
            print(f"[INFO] All pages in range {start_page}-{end_page if end_page else total_pages} already exist in JSON.")
            # Markdownが存在しない、またはJSONが更新された場合は再生成
            if not output_md_path.exists() or len(existing_data) > 0: # 常に再生成で良い
                 print(f"[INFO] Regenerating Markdown from existing JSON...")
                 markdown_content = json_to_markdown(existing_data)
                 with open(output_md_path, "w", encoding="utf-8") as f:
                     f.write(markdown_content)
                 print(f"[SUCCESS] Generated Markdown to: {output_md_path}")
            return

        print(f"[INFO] Processing {len(pages_to_process)} missing pages: {pages_to_process}")

        # 1. 事前に全バッチのデータを準備（PDFの切り出し）
        batch_tasks = []
        
        # pages_to_processをbatch_sizeごとに分割
        for i in range(0, len(pages_to_process), batch_size):
            chunk = pages_to_process[i : i + batch_size]
            
            # 指定範囲のページを含む新しいPDFを作成
            new_doc = fitz.open()
            for p_num in chunk:
                # p_num is 1-based, fitz uses 0-based
                new_doc.insert_pdf(doc, from_page=p_num-1, to_page=p_num-1)
            
            page_bytes = new_doc.tobytes()
            new_doc.close()
            
            # (page_mapping, page_bytes)
            batch_tasks.append((chunk, page_bytes))

        print(f"[INFO] Total batches to process: {len(batch_tasks)}")

        # 2. Batch APIを使用して一括処理
        generation_config = types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        )
        
        new_results = run_batch_api_ocr(batch_tasks, generation_config)

        # 既存データと結合
        all_pages_data = existing_data + new_results
        
        # 全ページのデータをJSONファイルとして保存
        if all_pages_data:
            # ページ番号順にソート
            all_pages_data.sort(key=lambda x: x.get("page_number", 0))
            
            # JSON保存
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(all_pages_data, f, ensure_ascii=False, indent=2)
            
            # Markdown変換と保存
            markdown_content = json_to_markdown(all_pages_data)
            with open(output_md_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            
            total_script_time = time.time() - script_start_time
            print(f"[SUCCESS] Updated JSON to: {output_json_path}")
            print(f"[SUCCESS] Updated Markdown to: {output_md_path}")
            print(f"[INFO] Total processing time for this PDF: {total_script_time:.1f}s")
        else:
            print("[ERROR] No data was extracted from the PDF.")

    except Exception as e:
        print(f"[ERROR] Processing failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # ドキュメントをクローズ
        doc.close()
