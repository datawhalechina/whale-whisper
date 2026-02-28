import {
  decideCaptureFallback,
  type CaptureFallbackDecision,
} from "./capture-startup.ts";

function run(name: string, fn: () => void) {
  try {
    fn();
    console.info(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

function expectDecision(
  actual: CaptureFallbackDecision,
  expected: CaptureFallbackDecision
) {
  const actualText = JSON.stringify(actual);
  const expectedText = JSON.stringify(expected);
  if (actualText !== expectedText) {
    throw new Error(`Expected ${expectedText} but received ${actualText}`);
  }
}

function expectEqual<T>(actual: T, expected: T) {
  if (actual !== expected) {
    throw new Error(`Expected ${String(expected)} but received ${String(actual)}`);
  }
}

run("falls back to media recorder when worklet init fails and media is supported", () => {
  const decision = decideCaptureFallback({
    workletError: new Error("worklet addModule failed"),
    mediaRecorderSupported: true,
  });

  expectDecision(decision, {
    mode: "media",
    error: null,
  });
});

run("returns actionable error when no fallback transport is available", () => {
  const decision = decideCaptureFallback({
    workletError: new Error("worklet addModule failed"),
    mediaRecorderSupported: false,
  });

  expectEqual(decision.mode, "none");
  expectEqual(decision.error, "worklet addModule failed");
});

run("normalizes non-error throw values", () => {
  const decision = decideCaptureFallback({
    workletError: "AudioWorklet is unavailable",
    mediaRecorderSupported: false,
  });

  expectEqual(decision.mode, "none");
  expectEqual(decision.error, "AudioWorklet is unavailable");
});
