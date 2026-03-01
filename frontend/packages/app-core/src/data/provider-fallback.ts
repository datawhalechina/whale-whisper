import type { ProviderCatalogEntry } from "./provider-catalog";

export const fallbackProviderCatalog: ProviderCatalogEntry[] = [
  {
    "id": "openrouter-ai",
    "label": "OpenRouter",
    "category": "chat",
    "icon": "i-lobe-icons:openrouter",
    "description": "openrouter.ai",
    "engineId": "openrouter",
    "defaults": {
      "baseUrl": "https://openrouter.ai/api/v1/"
    },
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true,
        "placeholder": "sk-..."
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "https://openrouter.ai/api/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "openai",
    "label": "OpenAI",
    "category": "chat",
    "icon": "i-lobe-icons:openai",
    "description": "OpenAI API compatible providers.",
    "engineId": "openai",
    "defaults": {
      "baseUrl": "https://api.openai.com/v1/",
      "model": "gpt-4o-mini"
    },
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true,
        "placeholder": "sk-..."
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "https://api.openai.com/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "groq",
    "label": "Groq",
    "category": "chat",
    "icon": "i-lobe-icons:groq",
    "description": "Groq API (OpenAI compatible).",
    "engineId": "groq",
    "defaults": {
      "baseUrl": "https://api.groq.com/openai/v1/"
    },
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true,
        "placeholder": "groq-..."
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "https://api.groq.com/openai/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "deepseek",
    "label": "DeepSeek",
    "category": "chat",
    "icon": "i-lobe-icons:deepseek",
    "description": "DeepSeek models.",
    "engineId": "deepseek",
    "defaults": {
      "baseUrl": "https://api.deepseek.com/v1/"
    },
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "https://api.deepseek.com/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "302-ai",
    "label": "302.AI",
    "category": "chat",
    "icon": "i-lobe-icons:ai302",
    "description": "302.AI gateway.",
    "engineId": 302,
    "defaults": {
      "baseUrl": "https://api.302.ai/v1/"
    },
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "https://api.302.ai/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "ollama",
    "label": "Ollama",
    "category": "chat",
    "icon": "i-lobe-icons:ollama",
    "description": "Local inference.",
    "engineId": "ollama",
    "defaults": {
      "baseUrl": "http://localhost:11434/v1/"
    },
    "fields": [
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "http://localhost:11434/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "lm-studio",
    "label": "LM Studio",
    "category": "chat",
    "icon": "i-lobe-icons:lmstudio",
    "description": "Local model server.",
    "engineId": "lmstudio",
    "defaults": {
      "baseUrl": "http://localhost:1234/v1/"
    },
    "fields": [
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "http://localhost:1234/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "vllm",
    "label": "vLLM",
    "category": "chat",
    "icon": "i-lobe-icons:vllm",
    "description": "vLLM inference server.",
    "engineId": "vllm",
    "defaults": {
      "baseUrl": "http://localhost:8000/v1/"
    },
    "fields": [
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "http://localhost:8000/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "openai-audio-transcription",
    "label": "OpenAI",
    "category": "transcription",
    "icon": "i-lobe-icons:openai",
    "description": "Whisper transcription.",
    "engineId": "openai-asr",
    "defaults": {
      "baseUrl": "https://api.openai.com/v1/",
      "model": "whisper-1"
    },
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true,
        "placeholder": "sk-..."
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "https://api.openai.com/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "openai-compatible",
    "label": "OpenAI Compatible",
    "category": "chat",
    "icon": "i-lobe-icons:openai",
    "description": "OpenAI-compatible endpoints.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "anthropic",
    "label": "Anthropic",
    "category": "chat",
    "icon": "i-lobe-icons:anthropic",
    "description": "Claude models.",
    "defaults": {
      "baseUrl": "https://api.anthropic.com/v1/"
    },
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "https://api.anthropic.com/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "google-generative-ai",
    "label": "Google",
    "category": "chat",
    "icon": "i-lobe-icons:gemini",
    "description": "Gemini models.",
    "defaults": {
      "baseUrl": "https://generativelanguage.googleapis.com/v1beta/"
    },
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "https://generativelanguage.googleapis.com/v1beta/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "alibaba-cloud-model-studio",
    "label": "Alibaba Cloud Model Studio",
    "category": "chat",
    "icon": "i-lobe-icons:alibabacloud",
    "description": "Alibaba Cloud model hosting.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "volcengine",
    "label": "Volcengine",
    "category": "chat",
    "icon": "i-lobe-icons:volcengine",
    "description": "Volcengine models.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "comet-api",
    "label": "Comet API",
    "category": "chat",
    "icon": "i-lobe-icons:cometapi",
    "description": "Comet API gateway.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "cerebras-ai",
    "label": "Cerebras",
    "category": "chat",
    "icon": "i-lobe-icons:cerebras",
    "description": "Cerebras models.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "together-ai",
    "label": "Together",
    "category": "chat",
    "icon": "i-lobe-icons:together",
    "description": "Together AI models.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "azure-ai-foundry",
    "label": "Azure AI Foundry",
    "category": "chat",
    "icon": "i-lobe-icons:microsoft",
    "description": "Azure AI Foundry.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "xai",
    "label": "xAI",
    "category": "chat",
    "icon": "i-lobe-icons:xai",
    "description": "xAI models.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "novita-ai",
    "label": "Novita",
    "category": "chat",
    "icon": "i-lobe-icons:novita",
    "description": "Novita AI platform.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "fireworks-ai",
    "label": "Fireworks",
    "category": "chat",
    "icon": "i-lobe-icons:fireworks",
    "description": "Fireworks AI.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "featherless-ai",
    "label": "Featherless",
    "category": "chat",
    "icon": "i-lobe-icons:featherless-ai",
    "description": "Featherless AI.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "cloudflare-workers-ai",
    "label": "Cloudflare Workers AI",
    "category": "chat",
    "icon": "i-lobe-icons:cloudflare",
    "description": "Cloudflare serverless AI.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "perplexity-ai",
    "label": "Perplexity",
    "category": "chat",
    "icon": "i-lobe-icons:perplexity",
    "description": "Perplexity models.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "mistral-ai",
    "label": "Mistral",
    "category": "chat",
    "icon": "i-lobe-icons:mistral",
    "description": "Mistral models.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "moonshot-ai",
    "label": "Moonshot",
    "category": "chat",
    "icon": "i-lobe-icons:moonshot",
    "description": "Moonshot models.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "modelscope",
    "label": "ModelScope",
    "category": "chat",
    "icon": "i-lobe-icons:modelscope",
    "description": "ModelScope hub.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "player2",
    "label": "Player2",
    "category": "chat",
    "icon": "i-lobe-icons:player2",
    "description": "Local gameplay assistant.",
    "defaults": {
      "baseUrl": "http://localhost:4315/v1/"
    },
    "fields": [
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "http://localhost:4315/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "volcengine-speech",
    "label": "Volcengine",
    "category": "speech",
    "icon": "i-lobe-icons:volcengine",
    "description": "volcengine.com",
    "engineId": "volcengine-speech",
    "defaults": {
      "baseUrl": "https://openspeech.bytedance.com/api/v1/tts",
      "model": "v1"
    },
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true,
        "placeholder": "sk-..."
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "https://openspeech.bytedance.com/api/v1/tts"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "options": [
          {
            "id": "v1",
            "label": "v1"
          }
        ]
      },
      {
        "id": "voice",
        "label": "Voice",
        "type": "select",
        "optionsSource": "voices"
      },
      {
        "id": "appId",
        "label": "App ID",
        "type": "text",
        "required": true,
        "scope": "extra"
      }
    ]
  },
  {
    "id": "alibaba-cloud-model-studio-speech",
    "label": "Alibaba Cloud Model Studio",
    "category": "speech",
    "icon": "i-lobe-icons:alibabacloud",
    "description": "bailian.console.aliyun.com",
    "engineId": "alibaba-cloud-model-studio-speech",
    "defaults": {
      "baseUrl": "https://dashscope.aliyuncs.com",
      "model": "cosyvoice-v1"
    },
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true,
        "default": "https://dashscope.aliyuncs.com"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "options": [
          {
            "id": "cosyvoice-v1",
            "label": "cosyvoice-v1"
          },
          {
            "id": "cosyvoice-v2",
            "label": "cosyvoice-v2"
          }
        ]
      },
      {
        "id": "voice",
        "label": "Voice",
        "type": "select",
        "optionsSource": "voices"
      }
    ]
  },
  {
    "id": "app-local-audio-speech",
    "label": "App (Local)",
    "category": "speech",
    "icon": "i-lobe-icons:huggingface",
    "description": "Local app speech runtime.",
    "fields": []
  },
  {
    "id": "browser-local-audio-speech",
    "label": "Browser (Local)",
    "category": "speech",
    "icon": "i-lobe-icons:huggingface",
    "description": "Local browser speech runtime.",
    "fields": []
  },
  {
    "id": "openai-compatible-audio-transcription",
    "label": "OpenAI Compatible",
    "category": "transcription",
    "icon": "i-lobe-icons:openai",
    "description": "OpenAI-compatible transcription.",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "required": true
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "aliyun-nls-transcription",
    "label": "Alibaba Cloud Model Studio",
    "category": "transcription",
    "icon": "i-lobe-icons:alibabacloud",
    "description": "Alibaba Bailian ASR transcription.",
    "engineId": "aliyun-nls-asr",
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true,
        "scope": "config"
      }
    ]
  },
  {
    "id": "comet-api-transcription",
    "label": "Comet API",
    "category": "transcription",
    "icon": "i-lobe-icons:cometapi",
    "description": "Comet API transcription.",
    "defaults": {
      "baseUrl": "https://api.cometapi.com/v1/"
    },
    "fields": [
      {
        "id": "apiKey",
        "label": "API Key",
        "type": "secret",
        "required": true
      },
      {
        "id": "baseUrl",
        "label": "Base URL",
        "type": "text",
        "default": "https://api.cometapi.com/v1/"
      },
      {
        "id": "model",
        "label": "Model",
        "type": "select",
        "optionsSource": "models"
      }
    ]
  },
  {
    "id": "app-local-audio-transcription",
    "label": "App (Local)",
    "category": "transcription",
    "icon": "i-lobe-icons:huggingface",
    "description": "Local app transcription runtime.",
    "fields": []
  },
  {
    "id": "browser-local-audio-transcription",
    "label": "Browser (Local)",
    "category": "transcription",
    "icon": "i-lobe-icons:huggingface",
    "description": "Local browser transcription runtime.",
    "fields": []
  }
];
