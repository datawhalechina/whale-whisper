const visibleSpeechProviderIds = new Set([
  "volcengine-speech",
  "alibaba-cloud-model-studio-speech",
  "browser-local-audio-speech",
  "app-local-audio-speech",
]);

export function isVisibleSpeechProviderId(providerId: string) {
  return visibleSpeechProviderIds.has(providerId);
}

export function filterVisibleSpeechProviders(providerIds: string[]) {
  return providerIds.filter((providerId) => isVisibleSpeechProviderId(providerId));
}
