export interface TtsChunkQueueResult {
  succeeded: number;
  failed: number;
  lastError: unknown | null;
}

export interface TtsChunkQueueContext {
  chunk: string;
  index: number;
  total: number;
}

export interface RunTtsChunkQueueOptions {
  onChunkError?: (error: unknown, context: TtsChunkQueueContext) => void;
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

export async function runTtsChunkQueue(
  chunks: string[],
  runChunk: (chunk: string, index: number, total: number) => Promise<void>,
  options?: RunTtsChunkQueueOptions
): Promise<TtsChunkQueueResult> {
  let succeeded = 0;
  let failed = 0;
  let lastError: unknown | null = null;

  for (let index = 0; index < chunks.length; index++) {
    const chunk = chunks[index];
    try {
      await runChunk(chunk, index, chunks.length);
      succeeded += 1;
    } catch (error) {
      if (isAbortError(error)) {
        throw error;
      }
      failed += 1;
      lastError = error;
      options?.onChunkError?.(error, {
        chunk,
        index,
        total: chunks.length,
      });
    }
  }

  if (succeeded === 0 && lastError) {
    throw lastError;
  }

  return { succeeded, failed, lastError };
}
