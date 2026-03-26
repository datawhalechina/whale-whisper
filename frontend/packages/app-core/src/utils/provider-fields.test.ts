import assert from "node:assert/strict";

import type { ProviderCatalogEntry } from "../data/provider-catalog.ts";
import { filterProviderFields } from "./provider-fields.ts";

function run(name: string, fn: () => void) {
  try {
    fn();
    console.info(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

function fieldIds(option: ProviderCatalogEntry) {
  return filterProviderFields(option).map((field) => field.id);
}

run("hides baseUrl when provider has default baseUrl in defaults", () => {
  const option: ProviderCatalogEntry = {
    id: "openai-compatible",
    label: "OpenAI Compatible",
    category: "chat",
    defaults: {
      baseUrl: "https://api.example.com/v1/",
    },
    fields: [
      { id: "apiKey", label: "API Key", type: "secret" },
      { id: "baseUrl", label: "Base URL", type: "text" },
      { id: "model", label: "Model", type: "select" },
    ],
  };
  assert.deepEqual(fieldIds(option), ["apiKey", "model"]);
});

run("hides baseUrl when baseUrl field itself has default", () => {
  const option: ProviderCatalogEntry = {
    id: "custom-provider",
    label: "Custom",
    category: "speech",
    fields: [
      { id: "apiKey", label: "API Key", type: "secret" },
      { id: "baseUrl", label: "Base URL", type: "text", default: "https://tts.example.com/" },
    ],
  };
  assert.deepEqual(fieldIds(option), ["apiKey"]);
});

run("keeps baseUrl when provider has no default baseUrl", () => {
  const option: ProviderCatalogEntry = {
    id: "manual-base-url",
    label: "Manual Base URL",
    category: "transcription",
    fields: [
      { id: "apiKey", label: "API Key", type: "secret" },
      { id: "baseUrl", label: "Base URL", type: "text" },
    ],
  };
  assert.deepEqual(fieldIds(option), ["apiKey", "baseUrl"]);
});
