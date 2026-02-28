const NON_RESTARTABLE_ERRORS = new Set([
  "not-allowed",
  "service-not-allowed",
  "audio-capture",
]);

type AutoRestartDecision = {
  userRequested: boolean;
  manuallyStopped: boolean;
  enabled: boolean;
  supported: boolean;
  useBrowserRecognition: boolean;
  lastErrorCode?: string | null;
};

export function shouldAutoRestartBrowserRecognition(options: AutoRestartDecision) {
  if (!options.userRequested) return false;
  if (options.manuallyStopped) return false;
  if (!options.enabled || !options.supported || !options.useBrowserRecognition) return false;
  if (!options.lastErrorCode) return true;
  return !NON_RESTARTABLE_ERRORS.has(options.lastErrorCode);
}

