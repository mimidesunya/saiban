const { GoogleGenAI } = require("@google/genai");
const { getApiKey } = require('./gemini_client');

class GeminiBatchProcessor {
    constructor() {
        const apiKey = getApiKey();
        if (!apiKey) throw new Error("API Key not found");
        this.ai = new GoogleGenAI({ apiKey });
    }

    /**
     * Runs an inline batch job.
     * @param {Array} requests Array of GenerateContentRequest objects
     * @param {string} modelId Model ID (e.g., "gemini-1.5-flash")
     * @param {string} displayName Optional display name for the job
     * @returns {Promise<Array>} Array of results (text content)
     */
    async runInlineBatch(requests, modelId, progressState, displayName = "batch-job") {
        // Check size estimate (rough check)
        const sizeEstimate = JSON.stringify(requests).length;
        console.log(`[バッチ] リクエストサイズ見積もり: ${(sizeEstimate / 1024 / 1024).toFixed(2)} MB`);
        
        if (sizeEstimate > 19 * 1024 * 1024) { // 19MB to be safe
            throw new Error(`バッチリクエストサイズ (${(sizeEstimate / 1024 / 1024).toFixed(2)} MB) がインラインバッチの安全制限を超えています。`);
        }

        console.log(`[バッチ] ${modelId} に対して ${requests.length} 件のリクエストでバッチジョブを作成中...`);
        
        let job;
        try {
            job = await this.ai.batches.create({
                model: modelId,
                src: requests,
                config: { displayName: displayName },
            });
        } catch (e) {
            console.error("バッチジョブの作成に失敗しました:", e);
            throw e;
        }

        console.log(`[バッチ] ジョブが作成されました: ${job.name}`);
        return await this.waitForCompletion(job.name, progressState);
    }

    async waitForCompletion(jobName, progressState) {
        const completed = new Set([
            "JOB_STATE_SUCCEEDED",
            "JOB_STATE_FAILED",
            "JOB_STATE_CANCELLED",
            "JOB_STATE_EXPIRED",
        ]);

        let cur = await this.ai.batches.get({ name: jobName });

        while (!completed.has(cur.state)) {
            if (progressState) {
                const elapsed = Date.now() - progressState.startTime;
                const avgTimePerRequest = progressState.completed > 0 ? elapsed / progressState.completed : 0;
                const remainingRequests = progressState.total - progressState.completed;
                const estimatedRemaining = avgTimePerRequest * remainingRequests;

                let timeInfo = `経過時間: ${this.formatTime(elapsed)}`;
                if (estimatedRemaining > 0) {
                    timeInfo += ` | 残り時間（予想）: ${this.formatTime(estimatedRemaining)}`;
                }
                console.log(`[バッチ] ステータス: ${cur.state} (${timeInfo})`);
            } else {
                console.log(`[バッチ] ステータス: ${cur.state} (30秒待機中...)`);
            }
            
            await new Promise(r => setTimeout(r, 30000)); // 30 seconds poll
            cur = await this.ai.batches.get({ name: cur.name });
        }

        console.log(`[バッチ] 最終ステータス: ${cur.state}`);

        if (cur.state === "JOB_STATE_SUCCEEDED") {
            if (cur.dest && cur.dest.inlinedResponses) {
                return cur.dest.inlinedResponses;
            } else {
                throw new Error("ジョブは成功しましたが、インラインレスポンスが見つかりませんでした。");
            }
        } else {
            throw new Error(`バッチジョブが失敗しました。ステータス: ${cur.state}`);
        }
    }

    formatTime(ms) {
        if (isNaN(ms) || ms < 0) return "00:00:00";
        const seconds = Math.floor((ms / 1000) % 60);
        const minutes = Math.floor((ms / (1000 * 60)) % 60);
        const hours = Math.floor(ms / (1000 * 60 * 60));
        return [hours, minutes, seconds].map(v => v.toString().padStart(2, '0')).join(':');
    }
}

module.exports = GeminiBatchProcessor;
