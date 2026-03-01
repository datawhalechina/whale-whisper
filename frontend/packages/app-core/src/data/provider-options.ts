export type ProviderCategory = "chat" | "speech" | "transcription";

export type SelectOption = {
  id: string;
  label: string;
  description?: string;
};

export type ProviderExtraField = {
  id: string;
  label: string;
  placeholder?: string;
  description?: string;
  required?: boolean;
  defaultValue?: string;
};

export type ProviderOption = {
  id: string;
  label: string;
  icon: string;
  description?: string;
  category: ProviderCategory;
  engineId?: string;
  defaultBaseUrl?: string;
  requiresApiKey?: boolean;
  requiresBaseUrl?: boolean;
  supportsModels?: boolean;
  supportsVoices?: boolean;
  modelOptions?: SelectOption[];
  voiceOptions?: SelectOption[];
  defaultModel?: string;
  defaultVoice?: string;
  extraFields?: ProviderExtraField[];
  defaultExtra?: Record<string, string>;
};

const whisperModels: SelectOption[] = [
  { id: "whisper-1", label: "whisper-1" },
];

export const chatProviderOptions: ProviderOption[] = [
  {
    id: "openrouter-ai",
    label: "OpenRouter",
    icon: "i-lobe-icons:openrouter",
    description: "openrouter.ai",
    category: "chat",
    engineId: "openrouter",
    defaultBaseUrl: "https://openrouter.ai/api/v1/",
    requiresApiKey: true,
    requiresBaseUrl: true,
    supportsModels: true,
  },
  {
    id: "openai",
    label: "OpenAI",
    icon: "i-lobe-icons:openai",
    description: "OpenAI API compatible providers.",
    category: "chat",
    engineId: "openai",
    defaultBaseUrl: "https://api.openai.com/v1/",
    requiresApiKey: true,
    requiresBaseUrl: true,
    supportsModels: true,
  },
  {
    id: "groq",
    label: "Groq",
    icon: "i-lobe-icons:groq",
    description: "Groq API (OpenAI compatible).",
    category: "chat",
    engineId: "groq",
    defaultBaseUrl: "https://api.groq.com/openai/v1/",
    requiresApiKey: true,
    requiresBaseUrl: true,
    supportsModels: true,
  },
  {
    id: "openai-compatible",
    label: "OpenAI Compatible",
    icon: "i-lobe-icons:openai",
    description: "OpenAI-compatible endpoints.",
    category: "chat",
    requiresApiKey: true,
    requiresBaseUrl: true,
    supportsModels: true,
  },
  {
    id: "anthropic",
    label: "Anthropic",
    icon: "i-lobe-icons:anthropic",
    description: "Claude models.",
    category: "chat",
    defaultBaseUrl: "https://api.anthropic.com/v1/",
    requiresApiKey: true,
    requiresBaseUrl: true,
  },
  {
    id: "google-generative-ai",
    label: "Google",
    icon: "i-lobe-icons:gemini",
    description: "Gemini models.",
    category: "chat",
    defaultBaseUrl: "https://generativelanguage.googleapis.com/v1beta/",
    requiresApiKey: true,
    requiresBaseUrl: true,
  },
  {
    id: "deepseek",
    label: "DeepSeek",
    icon: "i-lobe-icons:deepseek",
    description: "DeepSeek models.",
    category: "chat",
    engineId: "deepseek",
    defaultBaseUrl: "https://api.deepseek.com/v1/",
    requiresApiKey: true,
  },
  {
    id: "302-ai",
    label: "302.AI",
    icon: "i-lobe-icons:ai302",
    description: "302.AI gateway.",
    category: "chat",
    engineId: "302",
    defaultBaseUrl: "https://api.302.ai/v1/",
    requiresApiKey: true,
  },
  {
    id: "comet-api",
    label: "Comet API",
    icon: "i-lobe-icons:cometapi",
    description: "Comet API gateway.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "cerebras-ai",
    label: "Cerebras",
    icon: "i-lobe-icons:cerebras",
    description: "Cerebras models.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "together-ai",
    label: "Together",
    icon: "i-lobe-icons:together",
    description: "Together AI models.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "azure-ai-foundry",
    label: "Azure AI Foundry",
    icon: "i-lobe-icons:microsoft",
    description: "Azure AI Foundry.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "xai",
    label: "xAI",
    icon: "i-lobe-icons:xai",
    description: "xAI models.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "vllm",
    label: "vLLM",
    icon: "i-lobe-icons:vllm",
    description: "vLLM inference server.",
    category: "chat",
    engineId: "vllm",
    defaultBaseUrl: "http://localhost:8000/v1/",
    requiresBaseUrl: true,
    supportsModels: true,
  },
  {
    id: "novita-ai",
    label: "Novita",
    icon: "i-lobe-icons:novita",
    description: "Novita AI platform.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "fireworks-ai",
    label: "Fireworks",
    icon: "i-lobe-icons:fireworks",
    description: "Fireworks AI.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "featherless-ai",
    label: "Featherless",
    icon: "i-lobe-icons:featherless-ai",
    description: "Featherless AI.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "cloudflare-workers-ai",
    label: "Cloudflare Workers AI",
    icon: "i-lobe-icons:cloudflare",
    description: "Cloudflare serverless AI.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "perplexity-ai",
    label: "Perplexity",
    icon: "i-lobe-icons:perplexity",
    description: "Perplexity models.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "mistral-ai",
    label: "Mistral",
    icon: "i-lobe-icons:mistral",
    description: "Mistral models.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "moonshot-ai",
    label: "Moonshot",
    icon: "i-lobe-icons:moonshot",
    description: "Moonshot models.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "modelscope",
    label: "ModelScope",
    icon: "i-lobe-icons:modelscope",
    description: "ModelScope hub.",
    category: "chat",
    requiresApiKey: true,
  },
  {
    id: "ollama",
    label: "Ollama",
    icon: "i-lobe-icons:ollama",
    description: "Local inference.",
    category: "chat",
    engineId: "ollama",
    defaultBaseUrl: "http://localhost:11434/v1/",
    requiresBaseUrl: true,
    supportsModels: true,
  },
  {
    id: "lm-studio",
    label: "LM Studio",
    icon: "i-lobe-icons:lmstudio",
    description: "Local model server.",
    category: "chat",
    engineId: "lmstudio",
    defaultBaseUrl: "http://localhost:1234/v1/",
    requiresBaseUrl: true,
    supportsModels: true,
  },
  {
    id: "player2",
    label: "Player2",
    icon: "i-lobe-icons:player2",
    description: "Local gameplay assistant.",
    category: "chat",
    defaultBaseUrl: "http://localhost:4315/v1/",
    requiresBaseUrl: true,
  },
];

export const speechProviderOptions: ProviderOption[] = [
  {
    id: "volcengine-speech",
    label: "Volcengine",
    icon: "i-lobe-icons:volcengine",
    description: "volcengine.com",
    category: "speech",
    requiresApiKey: true,
    requiresBaseUrl: true,
    supportsModels: true,
    supportsVoices: true,
    modelOptions: [{ id: "v1", label: "v1" }],
    defaultModel: "v1",
    defaultBaseUrl: "https://openspeech.bytedance.com/api/v1/tts",
  },
  {
    id: "alibaba-cloud-model-studio-speech",
    label: "Alibaba Cloud Model Studio",
    icon: "i-lobe-icons:alibabacloud",
    description: "bailian.console.aliyun.com",
    category: "speech",
    engineId: "alibaba-cloud-model-studio-speech",
    requiresApiKey: true,
    requiresBaseUrl: true,
    supportsModels: true,
    supportsVoices: true,
    modelOptions: [
      { id: "cosyvoice-v1", label: "cosyvoice-v1" },
      { id: "cosyvoice-v2", label: "cosyvoice-v2" },
    ],
    defaultModel: "cosyvoice-v1",
    defaultBaseUrl: "https://dashscope.aliyuncs.com",
  },
  {
    id: "app-local-audio-speech",
    label: "App (Local)",
    icon: "i-lobe-icons:huggingface",
    description: "Local app speech runtime.",
    category: "speech",
  },
  {
    id: "browser-local-audio-speech",
    label: "Browser (Local)",
    icon: "i-lobe-icons:huggingface",
    description: "Local browser speech runtime.",
    category: "speech",
  },
];

export const transcriptionProviderOptions: ProviderOption[] = [
  {
    id: "openai-audio-transcription",
    label: "OpenAI",
    icon: "i-lobe-icons:openai",
    description: "Whisper transcription.",
    category: "transcription",
    engineId: "openai-asr",
    defaultBaseUrl: "https://api.openai.com/v1/",
    requiresApiKey: true,
    requiresBaseUrl: true,
    supportsModels: true,
    modelOptions: whisperModels,
    defaultModel: "whisper-1",
  },
  {
    id: "openai-compatible-audio-transcription",
    label: "OpenAI Compatible",
    icon: "i-lobe-icons:openai",
    description: "OpenAI-compatible transcription.",
    category: "transcription",
    requiresApiKey: true,
    requiresBaseUrl: true,
  },
  {
    id: "aliyun-nls-transcription",
    label: "Alibaba Cloud Model Studio",
    icon: "i-lobe-icons:alibabacloud",
    description: "Alibaba Bailian ASR transcription.",
    category: "transcription",
    engineId: "aliyun-nls-asr",
  },
  {
    id: "comet-api-transcription",
    label: "Comet API",
    icon: "i-lobe-icons:cometapi",
    description: "Comet API transcription.",
    category: "transcription",
    requiresApiKey: true,
  },
  {
    id: "app-local-audio-transcription",
    label: "App (Local)",
    icon: "i-lobe-icons:huggingface",
    description: "Local app transcription runtime.",
    category: "transcription",
  },
  {
    id: "browser-local-audio-transcription",
    label: "Browser (Local)",
    icon: "i-lobe-icons:huggingface",
    description: "Local browser transcription runtime.",
    category: "transcription",
  },
];

export const allProviderOptions: ProviderOption[] = [
  ...chatProviderOptions,
  ...speechProviderOptions,
  ...transcriptionProviderOptions,
];
