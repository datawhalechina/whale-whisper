interface TtsChunkQueueResult {
  succeeded: number;
  failed: number;
  lastError: unknown | null;
}

interface TtsChunkQueueContext {
  chunk: string;
  index: number;
  total: number;
}

export class TtsChunkQueueError extends Error {
  context: TtsChunkQueueContext;
  originalError: unknown;

  constructor(error: unknown, context: TtsChunkQueueContext) {
    const message = error instanceof Error ? error.message : String(error);
    super(`TTS chunk failed at ${context.index + 1}/${context.total}: ${message}`);
    this.name = "TtsChunkQueueError";
    this.context = context;
    this.originalError = error;
  }
}

interface RunTtsChunkQueueOptions {
  onChunkError?: (error: unknown, context: TtsChunkQueueContext) => void;
  stopOnError?: boolean;
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
      const context = {
        chunk,
        index,
        total: chunks.length,
      };
      options?.onChunkError?.(error, context);
      if (options?.stopOnError) {
        throw new TtsChunkQueueError(error, context);
      }
    }
  }

  if (succeeded === 0 && lastError) {
    throw lastError;
  }

  return { succeeded, failed, lastError };
}
