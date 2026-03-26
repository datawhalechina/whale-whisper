import type { ProviderCatalogEntry, ProviderField } from "../data/provider-catalog";

function resolveFieldDefault(field?: ProviderField) {
  if (!field || field.default === undefined || field.default === null) return "";
  return String(field.default).trim();
}

function hasDefaultBaseUrl(option?: ProviderCatalogEntry) {
  const defaultBaseUrl = option?.defaults?.baseUrl?.trim();
  if (defaultBaseUrl) {
    return true;
  }
  const baseUrlField = option?.fields?.find((field) => field.id === "baseUrl");
  return Boolean(resolveFieldDefault(baseUrlField));
}

export function filterProviderFields(option?: ProviderCatalogEntry): ProviderField[] {
  const fields = option?.fields ?? [];
  if (!hasDefaultBaseUrl(option)) {
    return fields;
  }
  return fields.filter((field) => field.id !== "baseUrl");
}
