const fs = require('fs');
const path = require('path');
const { PDFDocument } = require('pdf-lib');
const GeminiBatchProcessor = require('./gemini_batch');

const MODEL_ID = "gemini-3-flash-preview"; 

function formatTime(ms) {
    const seconds = Math.floor(ms / 1000);
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return [h, m, s].map(v => v.toString().padStart(2, '0')).join(':');
}

function getOcrPrompt(numPages, contextInstruction = "") {
    return `
# ROLE
High-precision OCR engine converting Japanese PDF pages to clean Markdown.

${contextInstruction}

# INPUT
${numPages} pages of a Japanese document.

# OUTPUT RULES
1. **Markdown Only**: No conversational text.
2. **No Skipping**: Even if the first page starts mid-sentence or mid-paragraph (continuation from a previous unprovided page), transcribe it completely from the very first character.
3. **Page Markers**:
   - **Start**: At the start of content, output \`### -- Begin Page N {StartStatus} --\`.
     - N: Batch page index (1-${numPages}).
     - {StartStatus}: "(Continuation)" if the text at the very top of the page is a direct continuation of a paragraph from the previous page (cut off mid-sentence without a line break), else empty.
   - **End**: At the end of content, output \`### -- End {PrintedPageInfo} {EndStatus} --\`.
     - {PrintedPageInfo}: "(Printed Page X)" if a printed page number X is found (CONVERT Kanji/Roman to Arabic). If not found, leave empty.
     - {EndStatus}: "(Continuation)" if the paragraph is cut off mid-sentence and continues to the next page without an explicit line break, else empty.
4. **Transcription Rules**:
   - **No Indentation**: Standard Markdown paragraphs.
   - **Numbers**: Convert ALL full-width numbers to half-width (e.g., "１" -> "1"). 
   - **Corrections**: Fix obvious OCR errors (0 vs O). Keep original typos with \`(-- as is)\`.
   - **Exclusions**: Omit printed page numbers from body.
     - **Redactions**: Replace blacked-out or redacted parts with "■".
     - **Margins**:
     - Headings text in margins: Format as \`(--# Text)\`.
     - Annotations/Notes in margins: Format as \`(--* Text)\`.
`;
}

function createOcrRequest(pdfBytes, numPages, contextInstruction = "") {
    const prompt = getOcrPrompt(numPages, contextInstruction);
    const base64Data = pdfBytes.toString('base64');

    return {
        contents: [
            {
                role: "user",
                parts: [
                    {
                        inlineData: {
                            mimeType: "application/pdf",
                            data: base64Data
                        }
                    },
                    { text: prompt }
                ]
            }
        ]
    };
}

async function runBatches(requests, metadata, batchProcessor, progressState) {
    let currentBatchRequests = [];
    let currentBatchMetadata = [];
    let currentBatchSize = 0;
    const MAX_BATCH_SIZE = 19 * 1024 * 1024; // 19MB
    const allResults = [];

    const processBatch = async () => {
        if (currentBatchRequests.length === 0) return;
        
        const batchCount = currentBatchRequests.length;
        const pagesInBatch = currentBatchMetadata.map(m => m.pages.join(',')).join(' | ');
        console.log(`[バッチ] ${batchCount} 件のリクエストを送信中 (ページ: ${pagesInBatch})...`);
        
        const results = await batchProcessor.runInlineBatch(currentBatchRequests, MODEL_ID, progressState);
        allResults.push(...results);
        
        progressState.completed += batchCount;
        const elapsed = Date.now() - progressState.startTime;
        const avgTimePerRequest = elapsed / progressState.completed;
        const remainingRequests = progressState.total - progressState.completed;
        const estimatedRemaining = avgTimePerRequest * remainingRequests;

        console.log(`[バッチ] 完了: ${progressState.completed}/${progressState.total} リクエスト`);
        console.log(`[バッチ] 経過時間: ${formatTime(elapsed)} | 残り時間（予想）: ${formatTime(estimatedRemaining)}`);
        
        currentBatchRequests = [];
        currentBatchMetadata = [];
        currentBatchSize = 0;
    };

    for (let i = 0; i < requests.length; i++) {
        const req = requests[i];
        const meta = metadata[i];
        const reqSize = JSON.stringify(req).length;
        if (currentBatchSize + reqSize > MAX_BATCH_SIZE) {
            await processBatch();
        }
        currentBatchRequests.push(req);
        currentBatchMetadata.push(meta);
        currentBatchSize += reqSize;
    }

    await processBatch();
    
    return allResults;
}

function extractPagesFromMarkdown(content) {
    const pageMap = new Map();
    const regex = /### -- Begin Page (\d+)/g;
    let match;
    const positions = [];

    while ((match = regex.exec(content)) !== null) {
        positions.push({ pageNum: parseInt(match[1], 10), index: match.index });
    }

    for (let i = 0; i < positions.length; i++) {
        const start = positions[i].index;
        const end = (i + 1 < positions.length) ? positions[i + 1].index : content.length;
        const pageContent = content.substring(start, end).trim();
        if (!pageContent.includes("[ERROR: OCR Failed")) {
            pageMap.set(positions[i].pageNum, pageContent);
        }
    }
    return pageMap;
}

async function pdfToText(pdfPath, batchSize = 5, startPage = 1, endPage = null, contextInstruction = "") {
    const pdfBuffer = fs.readFileSync(pdfPath);
    const srcDoc = await PDFDocument.load(pdfBuffer);
    const totalPages = srcDoc.getPageCount();
    
    const actualEndPage = endPage || totalPages;
    console.log(`[情報] 処理開始: ${pdfPath} (${totalPages} ページ中 ${startPage} から ${actualEndPage} ページまで)`);

    const errorPath = pdfPath.replace(/\.pdf$/i, "_ERROR_paged.md");
    const normalPath = pdfPath.replace(/\.pdf$/i, "_paged.md");
    
    let pageMap = new Map();
    if (fs.existsSync(errorPath)) {
        const existingContent = fs.readFileSync(errorPath, 'utf-8');
        pageMap = extractPagesFromMarkdown(existingContent);
        if (pageMap.size > 0) {
            console.log(`[情報] ${errorPath} から再開します (${pageMap.size} ページ完了済み)`);
        }
    }

    const pageIndices = [];
    for (let i = startPage; i <= actualEndPage; i++) {
        if (!pageMap.has(i)) {
            pageIndices.push(i);
        }
    }

    if (pageIndices.length === 0) {
        console.log(`[情報] すべての対象ページは既に完了しています。`);
    }

    // 1. Prepare all requests
    const requests = [];
    const batchMetadata = [];
    
    for (let i = 0; i < pageIndices.length; i += batchSize) {
        const batch = pageIndices.slice(i, i + batchSize);

        const newDoc = await PDFDocument.create();
        for (const pNum of batch) {
            const [copiedPage] = await newDoc.copyPages(srcDoc, [pNum - 1]);
            newDoc.addPage(copiedPage);
        }

        const batchPdfBytes = await newDoc.save();
        requests.push(createOcrRequest(Buffer.from(batchPdfBytes), batch.length, contextInstruction));
        batchMetadata.push({ startPage: batch[0], numPages: batch.length, pages: batch });
    }

    // 2. Run Batch(es) with Retry Logic
    const batchProcessor = new GeminiBatchProcessor();
    let pendingIndices = requests.map((_, i) => i);
    let retryCount = 0;
    const MAX_RETRIES = 3;

    const progressState = {
        completed: 0,
        total: requests.length,
        startTime: Date.now()
    };

    while (pendingIndices.length > 0) {
        if (retryCount >= MAX_RETRIES) {
            console.error(`[エラー] リトライ上限に達しました。${pendingIndices.length} 件のバッチが失敗しました。`);
            break;
        }
        
        if (retryCount > 0) {
            console.log(`[情報] ${pendingIndices.length} 件のバッチをリトライ中 (試行 ${retryCount}/${MAX_RETRIES})...`);
        }

        const currentRequests = pendingIndices.map(i => requests[i]);
        const currentMetadata = pendingIndices.map(i => batchMetadata[i]);
        const batchResults = await runBatches(currentRequests, currentMetadata, batchProcessor, progressState);

        const nextPendingIndices = [];

        for (let i = 0; i < batchResults.length; i++) {
            const originalIndex = pendingIndices[i];
            const result = batchResults[i];
            const meta = batchMetadata[originalIndex];
            
            let success = false;
            let text = "";

            if (!result.error && result.response?.candidates?.[0]?.content?.parts) {
                text = result.response.candidates[0].content.parts.map(p => p.text).join('');
                
                // Validation
                const beginCount = (text.match(/### -- Begin Page \d+/g) || []).length;
                const endCount = (text.match(/### -- End/g) || []).length;

                if (beginCount === meta.numPages && endCount === meta.numPages) {
                    success = true;
                } else {
                    console.warn(`[警告] バッチ ${originalIndex} (ページ ${meta.pages.join(',')}) の検証に失敗しました。期待されるマーカー数: ${meta.numPages}, 実際: 開始:${beginCount}, 終了:${endCount}。`);
                }
            } else {
                console.warn(`[警告] バッチ ${originalIndex} APIエラー: ${JSON.stringify(result.error || "内容なし")}`);
            }

            if (success) {
                // Fix page numbers (Relative -> Absolute)
                const absoluteText = text.replace(/### -- Begin Page (\d+)/g, (match, p1) => {
                    const relativePage = parseInt(p1, 10);
                    const absolutePage = meta.pages[relativePage - 1];
                    return `### -- Begin Page ${absolutePage}`;
                });
                
                const batchPages = extractPagesFromMarkdown(absoluteText);
                for (const [pNum, pContent] of batchPages) {
                    pageMap.set(pNum, pContent);
                }
            } else {
                nextPendingIndices.push(originalIndex);
            }
        }

        pendingIndices = nextPendingIndices;
        retryCount++;
    }

    // 3. Assemble results
    let allMarkdown = "";
    let hasError = false;
    for (let i = startPage; i <= actualEndPage; i++) {
        if (pageMap.has(i)) {
            allMarkdown += pageMap.get(i) + "\n\n";
        } else {
            allMarkdown += `### -- Begin Page ${i} --\n\n[ERROR: OCR Failed for page ${i}]\n\n`;
            hasError = true;
        }
    }

    if (hasError) {
        fs.writeFileSync(errorPath, allMarkdown, 'utf-8');
        console.log(`[警告] エラーを含んだ状態で ${errorPath} に保存されました`);
        if (fs.existsSync(normalPath)) fs.unlinkSync(normalPath);
        return errorPath;
    } else {
        fs.writeFileSync(normalPath, allMarkdown, 'utf-8');
        console.log(`[成功] ${normalPath} に保存されました`);
        if (fs.existsSync(errorPath)) fs.unlinkSync(errorPath);
        return normalPath;
    }
}

module.exports = {
    pdfToText,
    getOcrPrompt
};
