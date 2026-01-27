export type ProviderCategory = "chat" | "speech" | "transcription";

export type SelectOption = {
  id: string;
  label: string;
  description?: string;
  icon?: string;
};

export type ProviderField = {
  id: string;
  label: string;
  type: string;
  required?: boolean;
  placeholder?: string;
  default?: string | number | boolean | null;
  description?: string;
  scope?: string;
  options?: SelectOption[];
  optionsSource?: string;
};

export type ProviderDefaults = {
  baseUrl?: string;
  model?: string;
  voice?: string;
};

export type ProviderCatalogEntry = {
  id: string;
  label: string;
  category: ProviderCategory;
  icon?: string;
  description?: string;
  engineId?: string;
  defaults?: ProviderDefaults;
  fields?: ProviderField[];
};

export type ProviderCatalogResponse = {
  providers: ProviderCatalogEntry[];
};
