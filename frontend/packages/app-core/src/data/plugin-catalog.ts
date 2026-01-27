export type PluginDesc = {
  id: string;
  name: string;
  version?: string;
  description?: string;
  providers?: string[];
  metadata?: Record<string, unknown>;
};

export type PluginCatalogResponse = {
  plugins: PluginDesc[];
};
