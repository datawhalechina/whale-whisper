import {
  normalizeTranscriptionLanguage,
  resolveInitialTranscriptionLanguage,
} from "./transcription-language.ts";

function run(name: string, fn: () => void) {
  try {
    fn();
    console.info(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

function expectEqual<T>(actual: T, expected: T) {
  if (actual !== expected) {
    throw new Error(`Expected ${String(expected)} but received ${String(actual)}`);
  }
}

run("normalizes short zh language token", () => {
  expectEqual(normalizeTranscriptionLanguage("zh"), "zh-CN");
});

run("normalizes short en language token", () => {
  expectEqual(normalizeTranscriptionLanguage("en"), "en-US");
});

run("keeps specific locale value", () => {
  expectEqual(normalizeTranscriptionLanguage("ja-JP"), "ja-JP");
});

run("falls back to english when language is missing", () => {
  expectEqual(resolveInitialTranscriptionLanguage(undefined), "en-US");
});

run("uses navigator language when available", () => {
  expectEqual(resolveInitialTranscriptionLanguage("zh-CN"), "zh-CN");
});
