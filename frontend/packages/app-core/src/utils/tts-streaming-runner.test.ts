import assert from "node:assert/strict";

import { runTtsChunkQueue, TtsChunkQueueError } from "./tts-streaming-runner.ts";

async function run(name: string, fn: () => Promise<void> | void) {
  try {
    await fn();
    console.info(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

await run("continues when one chunk fails", async () => {
  const processed: string[] = [];
  const result = await runTtsChunkQueue(["A", "B", "C"], async (chunk) => {
    if (chunk === "B") {
      const error = new Error("Bad gateway") as Error & { status?: number };
      error.status = 502;
      throw error;
    }
    processed.push(chunk);
  });

  assert.deepEqual(processed, ["A", "C"]);
  assert.equal(result.succeeded, 2);
  assert.equal(result.failed, 1);
});

await run("throws when every chunk fails", async () => {
  await assert.rejects(
    async () => {
      await runTtsChunkQueue(["A", "B"], async () => {
        const error = new Error("Always fail");
        throw error;
      });
    },
    /Always fail/
  );
});

await run("does not swallow AbortError", async () => {
  await assert.rejects(
    async () => {
      await runTtsChunkQueue(["A"], async () => {
        throw new DOMException("Aborted", "AbortError");
      });
    },
    (error: unknown) =>
      error instanceof DOMException &&
      error.name === "AbortError"
  );
});

await run("stops on first chunk failure when stopOnError is enabled", async () => {
  const processed: string[] = [];
  await assert.rejects(
    async () => {
      await runTtsChunkQueue(
        ["A", "B", "C"],
        async (chunk) => {
          if (chunk === "B") {
            throw new Error("B failed");
          }
          processed.push(chunk);
        },
        { stopOnError: true }
      );
    },
    (error: unknown) => {
      if (!(error instanceof TtsChunkQueueError)) return false;
      assert.equal(error.context.index, 1);
      assert.equal(error.context.chunk, "B");
      return true;
    }
  );
  assert.deepEqual(processed, ["A"]);
});
