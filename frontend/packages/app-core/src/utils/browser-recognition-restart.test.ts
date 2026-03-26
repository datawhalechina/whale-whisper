import assert from "node:assert/strict";

import { shouldAutoRestartBrowserRecognition } from "./browser-recognition-restart.ts";

function run(name: string, fn: () => void) {
  try {
    fn();
    console.info(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

run("restarts when user session is active and no fatal error", () => {
  assert.equal(
    shouldAutoRestartBrowserRecognition({
      userRequested: true,
      manuallyStopped: false,
      enabled: true,
      supported: true,
      useBrowserRecognition: true,
      lastErrorCode: null,
    }),
    true
  );
});

run("does not restart after manual stop", () => {
  assert.equal(
    shouldAutoRestartBrowserRecognition({
      userRequested: true,
      manuallyStopped: true,
      enabled: true,
      supported: true,
      useBrowserRecognition: true,
      lastErrorCode: null,
    }),
    false
  );
});

run("does not restart on microphone permission denial", () => {
  assert.equal(
    shouldAutoRestartBrowserRecognition({
      userRequested: true,
      manuallyStopped: false,
      enabled: true,
      supported: true,
      useBrowserRecognition: true,
      lastErrorCode: "not-allowed",
    }),
    false
  );
});

