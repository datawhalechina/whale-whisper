export type CaptureFallbackDecision = {
  mode: "media" | "none";
  error: string | null;
};

type CaptureFallbackInput = {
  workletError: unknown;
  mediaRecorderSupported: boolean;
};

function normalizeError(error: unknown) {
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }
  return "Audio capture initialization failed.";
}

export function decideCaptureFallback(
  input: CaptureFallbackInput
): CaptureFallbackDecision {
  if (input.mediaRecorderSupported) {
    return {
      mode: "media",
      error: null,
    };
  }

  return {
    mode: "none",
    error: normalizeError(input.workletError),
  };
}
