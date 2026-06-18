import { defineStore, storeToRefs } from "pinia";
import { computed, onScopeDispose, ref, watch } from "vue";

import { useLlmmarkerParser } from "../composables/llmmarkerParser";
import { useI18n } from "../composables/use-i18n";
import { appConfig } from "../config";
import { createChatSocket } from "../services/ws";
import type { ClientEvent } from "../services/ws";
import type { AgentStreamEvent } from "../services/agent";
import { streamAgent } from "../services/agent";
import { buildActionTokenPrompt } from "../utils/action-token-prompt";
import { resolveModelMappingKey } from "../utils/model-mapping-key";
import { buildSessionMetadata } from "../utils/session-metadata";
import { useAgentStore } from "./agent";
import { useLocaleStore } from "./locale";
import { usePersonaCardStore } from "./persona-cards";
import { useProvidersStore } from "./providers";
import { useSettingsStore } from "./settings";
import { useDisplayModelsStore } from "./display-models";
import { useChatSessionsStore } from "./chat-sessions";
import { useLive2dModelMappingsStore } from "./live2d-model-mappings";
import { useStageModelCapabilitiesStore } from "./stage-model-capabilities";
import type { ChatAssistantMessage, ChatHistoryItem } from "../types/chat";

type SocketStatus = "disconnected" | "connecting" | "connected" | "error";

export const useChatStore = defineStore("chat", () => {
  const wsUrl = appConfig.wsUrl;
  const wsToken = appConfig.wsToken;
  const wsModuleName = appConfig.wsModuleName;
  const userId = appConfig.userId;
  const profileId = appConfig.profileId;

  const sessionsStore = useChatSessionsStore();
  const { activeSessionId, activeSession } = storeToRefs(sessionsStore);
  const sessionId = computed(() => activeSession.value?.sessionId ?? "");
  const messages = computed(() => activeSession.value?.messages ?? []);
  sessionsStore.ensureActiveSession();
  const streamingMessage = ref<ChatAssistantMessage | null>(null);
  const sending = ref(false);
  const sessionReady = ref(false);
  const pendingEvents = ref<ClientEvent[]>([]);
  const tokenLiteralHooks = ref<Array<(literal: string) => void | Promise<void>>>([]);
  const tokenSpecialHooks = ref<Array<(special: string) => void | Promise<void>>>([]);
  const assistantFinalHooks = ref<
    Array<(message: ChatAssistantMessage) => void | Promise<void>>
  >([]);

  const settingsStore = useSettingsStore();
  const providersStore = useProvidersStore();
  const agentStore = useAgentStore();
  const personaStore = usePersonaCardStore();
  const displayModelsStore = useDisplayModelsStore();
  const stageModelCapabilities = useStageModelCapabilitiesStore();
  const live2dModelMappings = useLive2dModelMappingsStore();
  const localeStore = useLocaleStore();
  const { t } = useI18n();
  const { chatProviderId } = storeToRefs(settingsStore);
  const { activePrompt } = storeToRefs(personaStore);
  const { activeModel } = storeToRefs(displayModelsStore);
  const { locale } = storeToRefs(localeStore);

  personaStore.initialize();
  const { agentEngineId, chatEnabled } = storeToRefs(agentStore);

  const socket = createChatSocket(wsUrl, {
    token: wsToken || undefined,
    moduleName: wsModuleName,
    possibleEvents: [
      "session.start",
      "input.text",
      "input.voice.start",
      "input.voice.chunk",
      "input.voice.end",
      "input.interrupt",
    ],
  });
  const status = computed<SocketStatus>(() => socket.status.value);
  let agentStreamController: AbortController | null = null;
  let expectActionTokens = false;
  let sawActionTokens = false;
  let lastMessageWasAgent = false;
  let lastAgentEngineId = "";
  const agentActionTokensSupport = ref<Record<string, boolean>>({});

  const statusLabel = computed(() => {
    if (status.value === "connected") return "Connected";
    if (status.value === "connecting") return "Connecting";
    if (status.value === "error") return "Error";
    return "Disconnected";
  });

  let eventQueue = Promise.resolve();
  const unsubscribe = socket.onEvent((event) => {
    eventQueue = eventQueue
      .then(() => handleEvent(event.type, event.data ?? event.payload ?? {}))
      .catch((error) => {
        console.error("Failed to handle chat event:", error);
      });
  });

  onScopeDispose(() => {
    unsubscribe();
    socket.disconnect();
    stopAgentStream(true);
  });

  watch(
    () => status.value,
    (next) => {
      if (next === "connected") {
        ensureSession();
        flushPendingEvents();
      } else if (next === "disconnected") {
        sessionReady.value = false;
      }
    },
    { immediate: true }
  );

  watch(
    () => activeSessionId.value,
    (next, prev) => {
      if (!next || next === prev) return;
      resetSessionState();
      if (status.value === "connected") {
        ensureSession();
      }
    }
  );

  function connect() {
    socket.connect();
  }

  function disconnect() {
    socket.disconnect();
    sessionReady.value = false;
    stopAgentStream(true);
  }

  function stopAgentStream(resetState = false) {
    if (agentStreamController) {
      agentStreamController.abort();
      agentStreamController = null;
    }
    if (resetState) {
      sending.value = false;
      streamingMessage.value = null;
      resetTokenParser();
    }
  }

  function resetSessionState() {
    sessionReady.value = false;
    pendingEvents.value = [];
    expectActionTokens = false;
    sawActionTokens = false;
    lastMessageWasAgent = false;
    lastAgentEngineId = "";
    stopAgentStream(true);
  }

function getActionPromptContext() {
  const model = activeModel.value;
  if (!model?.id) return undefined;
  if (model.format === "live2d") {
    const caps = stageModelCapabilities.getLive2dCapabilities(model.id);
    const mappingKey = resolveModelMappingKey(model);
    const mapping = live2dModelMappings.getMapping(mappingKey);
    return {
      format: "live2d",
      motions: caps?.motions,
      expressions: caps?.expressions,
      emotes: mapping?.emotes,
    };
  }
  if (model.format === "vrm") {
    const caps = stageModelCapabilities.getVrmCapabilities(model.id);
    return { format: "vrm", expressions: caps?.expressions };
  }
  return undefined;
}

function buildDeveloperPrompt() {
  const prompt = activePrompt.value?.trim();
  if (!settingsStore.stageActionTokensEnabled) {
    return prompt || "";
  }
  const override = settingsStore.stageActionTokensPrompt?.trim();
  const actionPrompt =
    override || buildActionTokenPrompt(locale.value || "en", getActionPromptContext());
  return [prompt, actionPrompt].filter(Boolean).join("\n\n");
}

function ensureSession() {
  if (!sessionId.value) {
    sessionsStore.ensureActiveSession();
  }
  if (status.value === "connected" && !sessionReady.value && sessionId.value) {
    const prompt = buildDeveloperPrompt();
    const sessionMeta = buildSessionMetadata({ locale: locale.value || undefined });
    enqueueEvent({
      type: "session.start",
      data: {
        session_id: sessionId.value,
        user_id: userId,
        profile_id: profileId,
        ...(sessionMeta ? { session_meta: sessionMeta } : {}),
        ...(prompt ? { developer_prompt: prompt } : {}),
      },
      sessionId: sessionId.value,
    });
  }
}

function send(text: string) {
  const trimmed = text.trim();
  if (!trimmed) return;
  if (!sessionId.value) {
    sessionsStore.ensureActiveSession();
  }

  prepareOutgoingMessage(trimmed, {
    expectActionTokens: settingsStore.stageActionTokensEnabled,
    agentMode: chatEnabled.value,
    engineId: agentEngineId.value,
  });

    if (chatEnabled.value) {
      void sendAgentMessage(trimmed);
      return;
    }

    if (status.value === "disconnected") {
      connect();
    }

    const providerPayload = providersStore.getProviderPayload(chatProviderId.value);

  const prompt = buildDeveloperPrompt();
    enqueueEvent({
      type: "input.text",
      data: {
        session_id: sessionId.value,
        user_id: userId,
        text: trimmed,
        provider: providerPayload,
        ...(prompt ? { developer_prompt: prompt } : {}),
      },
      sessionId: sessionId.value,
    });
  }

function prepareOutgoingMessage(
  text: string,
  options?: { expectActionTokens?: boolean; agentMode?: boolean; engineId?: string }
) {
  pushMessage({ role: "user", content: text });
  sending.value = true;
  streamingMessage.value = null;
  resetTokenParser();
  expectActionTokens = Boolean(options?.expectActionTokens);
  lastMessageWasAgent = Boolean(options?.agentMode);
  lastAgentEngineId = options?.engineId ?? "";
  sawActionTokens = false;
}

  async function sendAgentMessage(text: string) {
    const engineId = agentEngineId.value;
    if (!engineId) {
      pushMessage({ role: "error", content: "Agent engine not configured." });
      sending.value = false;
      return;
    }

    stopAgentStream();
    const controller = new AbortController();
    agentStreamController = controller;
    let streamDone = false;
    const isCurrent = () => agentStreamController === controller;

    const finalizeOnce = async () => {
      if (streamDone || !isCurrent()) return;
      streamDone = true;
      await finalizeAssistantText("");
    };

  const config = {
    ...sanitizeAgentConfig(agentStore.getEngineConfig(engineId)),
  };
  const sessionConversationId = sessionsStore.getAgentConversationId(engineId);
  if (sessionConversationId) {
    config.conversation_id = sessionConversationId;
  } else if ("conversation_id" in config) {
    delete config.conversation_id;
  }
  if (settingsStore.stageActionTokensEnabled) {
    const override = settingsStore.stageActionTokensPrompt?.trim();
    config.action_tokens_enabled = true;
    config.action_tokens_prompt =
      override || buildActionTokenPrompt(locale.value || "en", getActionPromptContext());
  }

    try {
      await streamAgent({
        engineId,
        text,
        config,
        sessionId: sessionId.value,
        userId,
        profileId,
        signal: controller.signal,
        onEvent: async (event) => {
          if (!isCurrent()) return;
          await handleAgentEvent(event, engineId, finalizeOnce);
        },
      });
      await finalizeOnce();
    } catch (error) {
      if (!isCurrent() || controller.signal.aborted) {
        return;
      }
      await finalizeOnce();
      const message =
        error instanceof Error ? error.message : "Agent request failed.";
      pushMessage({ role: "error", content: message });
    } finally {
      if (isCurrent()) {
        agentStreamController = null;
      }
    }
  }

  async function handleAgentEvent(
    event: AgentStreamEvent,
    engineId: string,
    finalize: () => Promise<void>
  ) {
    const payload =
      event && typeof event.data === "object" && event.data !== null
        ? (event.data as Record<string, any>)
        : {};
    const rawText = typeof event.data === "string" ? event.data : "";

  if (event.event === "conversation.id") {
    const conversationId =
      payload.conversation_id || payload.conversationId || payload.id;
    if (conversationId) {
      sessionsStore.setAgentConversationId(engineId, String(conversationId));
    }
    return;
  }

  if (event.event === "capabilities" || event.event === "agent.capabilities") {
    const supported =
      payload.action_tokens === true ||
      payload.actionTokens === true ||
      payload.action_tokens_supported === true ||
      payload.actionTokensSupported === true;
    if (supported && engineId) {
      agentActionTokensSupport.value = {
        ...agentActionTokensSupport.value,
        [engineId]: true,
      };
    }
    return;
  }

    if (event.event === "message.delta") {
      const delta = payload.text || rawText || "";
      if (delta) {
        await consumeAssistantDelta(String(delta));
      }
      return;
    }

    if (event.event === "message.done") {
      await finalize();
      return;
    }

    if (event.event === "error") {
      await finalize();
      pushMessage({ role: "error", content: payload.message || rawText || "Agent error." });
      return;
    }
  }

  function sanitizeAgentConfig(config: Record<string, unknown>) {
    return Object.entries(config ?? {}).reduce<Record<string, unknown>>((acc, [key, value]) => {
      if (value === undefined || value === null) return acc;
      if (typeof value === "string" && value.trim() === "") return acc;
      acc[key] = value;
      return acc;
    }, {});
  }

  async function handleEvent(type: string, payload: Record<string, any>) {
    if (type === "session.ready" || type === "session.started") {
      sessionReady.value = true;
      return;
    }

    if (type === "output.chat.delta") {
      await consumeAssistantDelta(payload.text || payload.delta || "");
      return;
    }

    if (type === "output.chat.complete") {
      await finalizeAssistantText(payload.text || payload.final || "");
      return;
    }

    if (type === "assistant.message" && payload.message) {
      pushAssistantMessage(payload.message);
      return;
    }

    if (type === "tool.call") {
      appendToolCall(payload.tool_name || payload.toolName, payload.args);
      return;
    }

    if (type === "tool.result") {
      appendToolResult(payload.id || payload.tool_call_id, payload.result);
      return;
    }

    if (type === "error") {
      pushMessage({ role: "error", content: payload.message || "Unknown error" });
      sending.value = false;
    }
  }

  function enqueueEvent(event: ClientEvent) {
    if (status.value !== "connected") {
      pendingEvents.value = [...pendingEvents.value, event];
      if (status.value === "disconnected") {
        connect();
      }
      return;
    }
    socket.send(event);
  }

  function flushPendingEvents() {
    if (!pendingEvents.value.length || status.value !== "connected") {
      return;
    }
    const queued = pendingEvents.value;
    pendingEvents.value = [];
    queued.forEach((event) => socket.send(event));
  }

  let tokenParser = createTokenParser();

  function createTokenParser() {
    return useLlmmarkerParser({
    minLiteralEmitLength: 1,
      onLiteral: async (literal) => {
        await emitTokenLiteralHooks(literal);
        appendAssistantText(literal);
      },
      onSpecial: async (special) => {
        await emitTokenSpecialHooks(special);
      },
    });
  }

function resetTokenParser() {
  tokenParser = createTokenParser();
}

async function parseTextWithTokens(text: string) {
  let literal = "";
  const parser = useLlmmarkerParser({
    minLiteralEmitLength: 1,
    onLiteral: async (chunk) => {
      literal += chunk;
    },
    onSpecial: async (special) => {
      await emitTokenSpecialHooks(special);
    },
  });
  await parser.consume(text);
  await parser.end();
  return literal;
}

  async function emitTokenLiteralHooks(literal: string) {
    for (const hook of tokenLiteralHooks.value) {
      await hook(literal);
    }
  }

async function emitTokenSpecialHooks(special: string) {
  for (const hook of tokenSpecialHooks.value) {
    await hook(special);
  }
  if (expectActionTokens) {
    sawActionTokens = true;
  }
}

  async function emitAssistantFinalHooks(message: ChatAssistantMessage) {
    for (const hook of assistantFinalHooks.value) {
      await hook(message);
    }
  }

  function onTokenLiteral(handler: (literal: string) => void | Promise<void>) {
    tokenLiteralHooks.value = [...tokenLiteralHooks.value, handler];
    return () => {
      tokenLiteralHooks.value = tokenLiteralHooks.value.filter((hook) => hook !== handler);
    };
  }

  function onTokenSpecial(handler: (special: string) => void | Promise<void>) {
    tokenSpecialHooks.value = [...tokenSpecialHooks.value, handler];
    return () => {
      tokenSpecialHooks.value = tokenSpecialHooks.value.filter((hook) => hook !== handler);
    };
  }

  function onAssistantFinal(handler: (message: ChatAssistantMessage) => void | Promise<void>) {
    assistantFinalHooks.value = [...assistantFinalHooks.value, handler];
    return () => {
      assistantFinalHooks.value = assistantFinalHooks.value.filter((hook) => hook !== handler);
    };
  }

  async function consumeAssistantDelta(delta: string) {
    if (!delta) return;
    await tokenParser.consume(delta);
  }

  function appendAssistantText(delta: string) {
    if (!delta) return;
    const message = ensureStreamingMessage();
    message.content = `${message.content}${delta}`;
    const textSlice = ensureTextSlice(message);
    textSlice.text += delta;
  }

  function appendToolCall(toolName?: string, args?: string) {
    if (!toolName) {
      return;
    }
    const message = ensureStreamingMessage();
    message.slices.push({
      type: "tool-call",
      toolCall: {
        toolName,
        args: args ? String(args) : "",
      },
    });
  }

  function appendToolResult(id?: string, result?: unknown) {
    if (!id) {
      return;
    }
    const message = ensureStreamingMessage();
    const normalizedResult =
      typeof result === "string" || Array.isArray(result) ? result : JSON.stringify(result ?? "");
    message.slices.push({
      type: "tool-call-result",
      id: String(id),
      result: normalizedResult,
    });
    message.tool_results.push({
      id: String(id),
      result: normalizedResult,
    });
  }

  function ensureTextSlice(message: ChatAssistantMessage) {
    if (!message.slices.length || message.slices[message.slices.length - 1].type !== "text") {
      message.slices.push({ type: "text", text: "" });
    }
    return message.slices[message.slices.length - 1];
  }

  function ensureStreamingMessage() {
    if (!streamingMessage.value) {
      streamingMessage.value = {
        id: createId(),
        role: "assistant",
        content: "",
        slices: [],
        tool_results: [],
        createdAt: Date.now(),
      };
    }
    return streamingMessage.value;
  }

  function pushAssistantMessage(message: Partial<ChatAssistantMessage>) {
    const normalized = {
      id: message.id ?? createId(),
      role: "assistant",
      content: message.content ?? "",
      slices: message.slices ?? [],
      tool_results: message.tool_results ?? [],
      createdAt: message.createdAt ?? Date.now(),
    } satisfies ChatAssistantMessage;

    sessionsStore.appendMessage(normalized);
    void emitAssistantFinalHooks(normalized);
  streamingMessage.value = null;
  sending.value = false;
  resetTokenParser();
  if (lastMessageWasAgent && expectActionTokens && !sawActionTokens) {
    pushMessage({
      role: "error",
      content: t("stage.actions.warn"),
    });
  }
  expectActionTokens = false;
  lastMessageWasAgent = false;
  lastAgentEngineId = "";
  sawActionTokens = false;
}

  async function finalizeAssistantText(text: string) {
    if (streamingMessage.value) {
      await tokenParser.end();
      const finalText = streamingMessage.value.content || text;
      const finalMessage = {
        ...streamingMessage.value,
        content: finalText,
      };
      sessionsStore.appendMessage(finalMessage);
      await emitAssistantFinalHooks(finalMessage);
    } else if (text) {
      const literalText = await parseTextWithTokens(text);
      const finalMessage: ChatAssistantMessage = {
        role: "assistant",
        content: literalText,
        slices: [{ type: "text", text: literalText }],
        tool_results: [],
        id: createId(),
        createdAt: Date.now(),
      };
      sessionsStore.appendMessage(finalMessage);
      await emitAssistantFinalHooks(finalMessage);
    }
    streamingMessage.value = null;
    sending.value = false;
    resetTokenParser();
  }

  function pushMessage(message: Omit<ChatHistoryItem, "id" | "createdAt">) {
    const entry: ChatHistoryItem = {
      ...message,
      id: createId(),
      createdAt: Date.now(),
    };
    sessionsStore.appendMessage(entry);
    return entry;
  }

  function cleanupMessages() {
    sessionsStore.clearActiveMessages();
    streamingMessage.value = null;
    stopAgentStream(true);
  }

  function reconnect() {
    disconnect();
    connect();
    ensureSession();
  }

  function createId() {
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  return {
    messages,
    streamingMessage,
    sending,
    status,
    statusLabel,
    sessionId,
    connect,
    disconnect,
    ensureSession,
    send,
    cleanupMessages,
    reconnect,
    onTokenLiteral,
    onTokenSpecial,
    onAssistantFinal,
  };
});
