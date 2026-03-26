<script setup lang="ts">
import { storeToRefs } from "pinia";
import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from "vue";
import { refDebounced, useMouse, useWindowSize } from "@vueuse/core";

import {
  StageViewport,
  provideStageI18n,
  useLive2d,
  useStageSettingsStore,
} from "@whalewhisper/stage-core";
import { useActionTokenPromptSync } from "@whalewhisper/app-core/composables/use-action-token-prompt-sync";
import { useChatStore } from "@whalewhisper/app-core/stores/chat";
import { useLive2dRuntime } from "@whalewhisper/app-core/stores/live2d-runtime";
import { useUiStore } from "@whalewhisper/app-core/stores/ui";
import DesktopSessionPanel from "./components/DesktopSessionPanel.vue";
import StageViewOverlay from "./components/StageViewOverlay.vue";
import { useCanvasPixelIsTransparentAtPoint } from "./utils/canvas-alpha";
import {
  getWindowBehavior,
  setClickThrough,
  setDragEnabled,
  setControlsBounds,
  listenDesktopHover,
  listenDesktopCursor,
  listenDesktopChat,
  listenDesktopActionToken,
  syncChatWindowBounds,
  openSettingsWindow,
} from "./services/desktop";

type WindowBehavior = {
  clickThrough: boolean;
  dragEnabled: boolean;
};

const mouse = useMouse();
const live2d = useLive2d();
const stageSettings = useStageSettingsStore();
const uiStore = useUiStore();
const chatStore = useChatStore();
const live2dRuntime = useLive2dRuntime();
const { stageDragEnabled, stageViewControlsEnabled } = storeToRefs(stageSettings);
const { sessionsOpen } = storeToRefs(uiStore);
const { scale, positionInPercentageString, modelRect } = storeToRefs(live2d);

provideStageI18n({
  t: (key: string) => {
    if (key === "stage.vrm.empty") {
      return "No VRM model loaded";
    }
    return key;
  },
});
useActionTokenPromptSync();

const windowBehavior = ref<WindowBehavior>({
  clickThrough: false,
  dragEnabled: false,
});
const controlsBoundsQueued = ref(false);
const controlsBounds = ref<{
  left: number;
  top: number;
  right: number;
  bottom: number;
} | null>(null);
const controlsRects = ref<DOMRect[]>([]);
const hoverFaded = ref(false);
const hasCursorState = ref(false);
const lastCursorEventAt = ref(0);
const cursorEventsActive = ref(false);
let cursorEventsTimer: number | null = null;
const cursorInsideWindow = ref(false);
const cursorClientX = ref(0);
const cursorClientY = ref(0);
const windowWidth = ref(0);
const windowHeight = ref(0);
const windowLeft = ref(0);
const windowTop = ref(0);
const windowScale = ref(1);
const clickThroughApplied = ref<boolean | null>(null);
const stageContainerRef = ref<HTMLElement | null>(null);
const stageViewportRef = ref<InstanceType<typeof StageViewport> | null>(null);
const stageCanvas = ref<HTMLCanvasElement | undefined>();
let unlistenHover: null | (() => void) = null;
let unlistenCursor: null | (() => void) = null;
let unlistenChat: null | (() => void) = null;
let unlistenActionToken: null | (() => void) = null;
let boundsTimer: number | null = null;
let canvasTimer: number | null = null;
const hoverFadeOpacity = 0.35;
const fadeOnHoverEnabled = ref(true);
const { width: viewportWidth, height: viewportHeight } = useWindowSize();
const controlsVisible = ref(false);
let controlsHideTimer: number | null = null;
const chatWindowVisible = ref(false);
const chatSyncQueued = ref(false);

const focusAt = computed(() => ({
  x: mouse.x.value,
  y: mouse.y.value,
}));

const stageXOffset = computed(() => positionInPercentageString.value.x);
const stageYOffset = computed(() => positionInPercentageString.value.y);
const isTransparent = useCanvasPixelIsTransparentAtPoint(
  () => stageCanvas.value,
  cursorClientX,
  cursorClientY,
  { threshold: 12, regionRadius: 25 }
);

const isInModelRect = computed(() => {
  if (!cursorInsideWindow.value) return false;
  const rect = modelRect.value;
  if (rect.right <= rect.left || rect.bottom <= rect.top) {
    return cursorInsideWindow.value;
  }
  return (
    cursorClientX.value >= rect.left &&
    cursorClientX.value <= rect.right &&
    cursorClientY.value >= rect.top &&
    cursorClientY.value <= rect.bottom
  );
});

const isOpaqueAtCursor = computed(() => {
  if (!cursorInsideWindow.value) return false;
  if (!stageCanvas.value) return isInModelRect.value;
  if (!isTransparent.value) return true;
  return isInModelRect.value;
});

const controlSize = computed(() => {
  const raw = 40 * (scale.value || 1);
  return Math.max(28, Math.min(44, raw));
});
const controlGap = 8;
const controlsVerticalOffset = -20;
const controlsHovering = computed(() => {
  if (!cursorInsideWindow.value) return false;
  if (!controlsRects.value.length) return false;
  return controlsRects.value.some(
    (rect) =>
      cursorClientX.value >= rect.left &&
      cursorClientX.value <= rect.right &&
      cursorClientY.value >= rect.top &&
      cursorClientY.value <= rect.bottom
  );
});
const controlsWindowVisible = ref(false);
const controlsSyncQueued = ref(false);
const isOutsideControls = computed(() => !controlsHovering.value);
const isOutsideControlsFor250Ms = refDebounced(isOutsideControls, 250);
const isOutsideWindow = computed(() => !cursorInsideWindow.value);
const borderThreshold = 30;
const isNearWindowBorder = computed(() => {
  if (!cursorInsideWindow.value) return false;
  const width = windowWidth.value;
  const height = windowHeight.value;
  if (!width || !height) return false;
  return (
    cursorClientX.value <= borderThreshold ||
    cursorClientY.value <= borderThreshold ||
    cursorClientX.value >= width - borderThreshold ||
    cursorClientY.value >= height - borderThreshold
  );
});
const isNearWindowBorderFor250Ms = refDebounced(isNearWindowBorder, 250);

const controlsPositionStyle = computed(() => {
  const rect = modelRect.value;
  const width = Math.max(0, viewportWidth.value || 0);
  const height = Math.max(0, viewportHeight.value || 0);
  const buttonSize = controlSize.value;
  const gap = controlGap;
  const containerWidth = buttonSize;
  const containerHeight = buttonSize * 3 + gap * 2;
  const margin = 12;
  const inset = 8;

  if (!width || !height || rect.right <= rect.left || rect.bottom <= rect.top) {
    const fallbackLeft = Math.max(margin, width - margin - containerWidth);
    const fallbackTop = Math.max(
      margin,
      height - margin - containerHeight + controlsVerticalOffset
    );
    return {
      left: `${fallbackLeft}px`,
      top: `${fallbackTop}px`,
    };
  }

  const targetLeft = Math.min(
    Math.max(rect.right - containerWidth - inset, margin),
    width - margin - containerWidth
  );
  const targetTop = Math.min(
    Math.max(
      rect.bottom - containerHeight - inset + controlsVerticalOffset,
      margin
    ),
    height - margin - containerHeight
  );
  return {
    left: `${targetLeft}px`,
    top: `${targetTop}px`,
  };
});


function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

const sessionsPanelStyle = computed(() => {
  const width = 280;
  const height = Math.min(360, Math.max(220, viewportHeight.value * 0.4));
  const gap = 12;
  const margin = 12;
  const fallbackLeft = Number.parseFloat(
    String(controlsPositionStyle.value.left || "0")
  );
  const fallbackTop = Number.parseFloat(
    String(controlsPositionStyle.value.top || "0")
  );
  const anchorLeft = controlsBounds.value?.left ?? fallbackLeft;
  const anchorTop = controlsBounds.value?.top ?? fallbackTop;
  const left = clamp(anchorLeft - width - gap, margin, viewportWidth.value - width - margin);
  const top = clamp(anchorTop - height + controlSize.value, margin, viewportHeight.value - height - margin);
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`,
  };
});

const chatWindowWidth = 240;
const chatWindowMinHeight = 260;
const chatWindowMaxHeight = 260;
const chatWindowGap = 0;
const chatWindowBottomGap = 0;
const chatWindowOffsetRatio = 0;

function resolveChatWindowBounds() {
  if (!hasCursorState.value) return null;
  const rect = modelRect.value;
  const scale = windowScale.value || 1;
  const rectValid = rect.right > rect.left && rect.bottom > rect.top;
  const modelHeight = rectValid ? rect.bottom - rect.top : 0;
  const height = clamp(
    Number.isFinite(modelHeight) && modelHeight > 0 ? modelHeight : chatWindowMinHeight,
    chatWindowMinHeight,
    chatWindowMaxHeight
  );
  const logicalWidth = Math.max(0, windowWidth.value || 0);
  const logicalHeight = Math.max(0, windowHeight.value || 0);
  const leftCandidate = rect.left - chatWindowWidth - chatWindowGap;
  let left = leftCandidate;
  const offsetY = modelHeight * chatWindowOffsetRatio;
  let top = rect.bottom - height + offsetY;
  if (logicalHeight > 0) {
    top = clamp(top, 0, Math.max(0, logicalHeight - height));
  }
  if (!rectValid) {
    left = (logicalWidth - chatWindowWidth) / 2;
    top = (logicalHeight - height) / 2;
    const maxLeft = Math.max(0, logicalWidth - chatWindowWidth);
    const maxTop = Math.max(0, logicalHeight - height);
    left = clamp(left, 0, maxLeft);
    top = clamp(top, 0, maxTop);
  }
  const x = Math.round(windowLeft.value + left * scale);
  const y = Math.round(windowTop.value + top * scale);
  const width = Math.round(chatWindowWidth * scale);
  const safeHeight = Math.round(height * scale);
  return { x, y, width, height: safeHeight };
}

function scheduleChatWindowSync() {
  if (!chatWindowVisible.value) return;
  if (chatSyncQueued.value) return;
  chatSyncQueued.value = true;
  requestAnimationFrame(() => {
    chatSyncQueued.value = false;
    const bounds = resolveChatWindowBounds();
    if (!bounds) return;
    void syncChatWindowBounds(bounds);
  });
}

function scheduleControlsWindowSync() {
  if (!controlsWindowVisible.value) return;
  if (controlsSyncQueued.value) return;
  controlsSyncQueued.value = true;
  requestAnimationFrame(() => {
    controlsSyncQueued.value = false;
    scheduleControlsBoundsSync();
  });
}

const shouldFadeOnModel = computed(() => {
  if (!fadeOnHoverEnabled.value) return false;
  if (!hasCursorState.value) return false;
  if (sessionsOpen.value) return false;
  if (stageViewControlsEnabled.value) return false;
  if (!isOutsideControlsFor250Ms.value) return false;
  if (isNearWindowBorderFor250Ms.value) return false;
  if (isOutsideWindow.value) return false;
  return isOpaqueAtCursor.value;
});

const shouldIgnoreCursor = computed(() => {
  if (!fadeOnHoverEnabled.value) return false;
  if (!hasCursorState.value) return false;
  if (sessionsOpen.value) return false;
  if (stageViewControlsEnabled.value) return false;
  if (!isOutsideControlsFor250Ms.value) return false;
  if (isNearWindowBorderFor250Ms.value) return false;
  if (!cursorEventsActive.value) return false;
  return true;
});

const showControls = computed(() => controlsVisible.value);

function markCursorEvent() {
  lastCursorEventAt.value = Date.now();
  cursorEventsActive.value = true;
  if (cursorEventsTimer) {
    window.clearTimeout(cursorEventsTimer);
  }
  cursorEventsTimer = window.setTimeout(() => {
    cursorEventsActive.value = false;
    cursorEventsTimer = null;
  }, 200);
}

function handleToggleSessions() {
  uiStore.toggleSessions();
}

function handleOpenSettings() {
  void openSettingsWindow();
}

function handleToggleViewControls() {
  stageViewControlsEnabled.value = !stageViewControlsEnabled.value;
}

async function refreshWindowBehavior() {
  const result = await getWindowBehavior();
  if (result) {
    windowBehavior.value = result;
  }
}

async function setWindowDragEnabled(enabled: boolean) {
  const next = await setDragEnabled(enabled);
  if (next) {
    windowBehavior.value = next;
  }
}

function syncControlsBounds() {
  const nodes = Array.from(
    document.querySelectorAll<HTMLElement>("[data-controls-hitbox]")
  );
  if (!nodes.length) {
    controlsBounds.value = null;
    controlsRects.value = [];
    void setControlsBounds(null);
    return;
  }
  const rects: DOMRect[] = [];
  let left = Number.POSITIVE_INFINITY;
  let top = Number.POSITIVE_INFINITY;
  let right = Number.NEGATIVE_INFINITY;
  let bottom = Number.NEGATIVE_INFINITY;
  for (const node of nodes) {
    const rect = node.getBoundingClientRect();
    if (
      !Number.isFinite(rect.width) ||
      !Number.isFinite(rect.height) ||
      rect.width <= 0 ||
      rect.height <= 0
    ) {
      continue;
    }
    rects.push(rect);
    left = Math.min(left, rect.left);
    top = Math.min(top, rect.top);
    right = Math.max(right, rect.right);
    bottom = Math.max(bottom, rect.bottom);
  }
  controlsRects.value = rects;
  if (!Number.isFinite(left) || !Number.isFinite(right)) {
    controlsBounds.value = null;
    void setControlsBounds(null);
    return;
  }
  controlsBounds.value = { left, top, right, bottom };
  void setControlsBounds({ left, top, right, bottom });
}

function scheduleControlsBoundsSync() {
  if (controlsBoundsQueued.value) return;
  controlsBoundsQueued.value = true;
  requestAnimationFrame(() => {
    controlsBoundsQueued.value = false;
    syncControlsBounds();
  });
}

function syncStageCanvas() {
  const canvas =
    stageViewportRef.value?.canvasElement?.() ??
    stageContainerRef.value?.querySelector("canvas") ??
    undefined;
  if (canvas !== stageCanvas.value) {
    stageCanvas.value = canvas || undefined;
  }
}

onMounted(async () => {
  void refreshWindowBehavior();
  stageDragEnabled.value = false;
  stageViewControlsEnabled.value = false;
  const initialBehavior = await setClickThrough(false);
  if (initialBehavior) {
    windowBehavior.value = initialBehavior;
  }
  clickThroughApplied.value = false;
  void setWindowDragEnabled(true);
  window.addEventListener("contextmenu", handleContextMenu);
  window.addEventListener("resize", scheduleControlsBoundsSync);
  scheduleControlsBoundsSync();
  boundsTimer = window.setInterval(syncControlsBounds, 250);
  syncStageCanvas();
  canvasTimer = window.setInterval(syncStageCanvas, 1000);
  listenDesktopCursor((payload) => {
    markCursorEvent();
    hasCursorState.value = true;
    const physicalWidth = payload.windowRight - payload.windowLeft;
    const physicalHeight = payload.windowBottom - payload.windowTop;
    const fallbackLogicalWidth = Math.max(1, window.innerWidth || 0);
    const fallbackLogicalHeight = Math.max(1, window.innerHeight || 0);
    const scaleX =
      physicalWidth > 0 && fallbackLogicalWidth > 0
        ? physicalWidth / fallbackLogicalWidth
        : 1;
    const scaleY =
      physicalHeight > 0 && fallbackLogicalHeight > 0
        ? physicalHeight / fallbackLogicalHeight
        : 1;
    const fallbackScale =
      Number.isFinite(scaleX) && Number.isFinite(scaleY)
        ? (scaleX + scaleY) / 2
        : window.devicePixelRatio || 1;
    const scale = payload.scaleFactor > 0 ? payload.scaleFactor : fallbackScale;
    windowLeft.value = payload.windowLeft;
    windowTop.value = payload.windowTop;
    windowScale.value = scale;
    cursorClientX.value = (payload.cursorX - payload.windowLeft) / scale;
    cursorClientY.value = (payload.cursorY - payload.windowTop) / scale;
    const logicalWidth = Math.max(1, physicalWidth / scale);
    const logicalHeight = Math.max(1, physicalHeight / scale);
    windowWidth.value = logicalWidth;
    windowHeight.value = logicalHeight;
    cursorInsideWindow.value =
      cursorClientX.value >= 0 &&
      cursorClientY.value >= 0 &&
      cursorClientX.value <= logicalWidth &&
      cursorClientY.value <= logicalHeight;
  }).then((unlisten) => {
    unlistenCursor = unlisten ?? null;
  });
  listenDesktopHover((payload) => {
    if (hasCursorState.value) return;
    hoverFaded.value = payload.faded;
  }).then((unlisten) => {
    unlistenHover = unlisten ?? null;
  });
  listenDesktopChat((payload) => {
    const action = payload?.action ?? "open";
    if (action === "toggle") {
      chatWindowVisible.value = !chatWindowVisible.value;
      scheduleChatWindowSync();
      return;
    }
    if (action === "close") {
      chatWindowVisible.value = false;
      return;
    }
    chatWindowVisible.value = true;
    scheduleChatWindowSync();
  }).then((unlisten) => {
    unlistenChat = unlisten ?? null;
  });

  listenDesktopActionToken((payload) => {
    void live2dRuntime.applySpecialToken(payload.token);
  }).then((unlisten) => {
    unlistenActionToken = unlisten ?? null;
  });
});

onUnmounted(() => {
  window.removeEventListener("contextmenu", handleContextMenu);
  window.removeEventListener("resize", scheduleControlsBoundsSync);
  if (controlsHideTimer) {
    window.clearTimeout(controlsHideTimer);
    controlsHideTimer = null;
  }
  if (boundsTimer) {
    window.clearInterval(boundsTimer);
    boundsTimer = null;
  }
  if (canvasTimer) {
    window.clearInterval(canvasTimer);
    canvasTimer = null;
  }
  if (cursorEventsTimer) {
    window.clearTimeout(cursorEventsTimer);
    cursorEventsTimer = null;
  }
  if (unlistenCursor) {
    unlistenCursor();
    unlistenCursor = null;
  }
  if (unlistenHover) {
    unlistenHover();
    unlistenHover = null;
  }
  if (unlistenChat) {
    unlistenChat();
    unlistenChat = null;
  }
  if (unlistenActionToken) {
    unlistenActionToken();
    unlistenActionToken = null;
  }
});

function handleContextMenu(event: MouseEvent) {
  event.preventDefault();
}

watch(stageViewControlsEnabled, async () => {
  await nextTick();
  scheduleControlsBoundsSync();
});

watch(chatWindowVisible, async () => {
  await nextTick();
  scheduleChatWindowSync();
});

watch(sessionsOpen, async () => {
  await nextTick();
  scheduleControlsBoundsSync();
});

watch([mouse.x, mouse.y, hasCursorState], () => {
  if (cursorEventsActive.value) return;
  const rect = stageContainerRef.value?.getBoundingClientRect();
  if (!rect) return;
  hasCursorState.value = true;
  const localX = mouse.x.value - rect.left;
  const localY = mouse.y.value - rect.top;
  cursorClientX.value = localX;
  cursorClientY.value = localY;
  cursorInsideWindow.value =
    localX >= 0 &&
    localY >= 0 &&
    localX <= rect.width &&
    localY <= rect.height;
  windowWidth.value = rect.width;
  windowHeight.value = rect.height;
  const screenX =
    typeof window.screenX === "number"
      ? window.screenX
      : (window as Window & { screenLeft?: number }).screenLeft ?? 0;
  const screenY =
    typeof window.screenY === "number"
      ? window.screenY
      : (window as Window & { screenTop?: number }).screenTop ?? 0;
  windowLeft.value = screenX;
  windowTop.value = screenY;
  windowScale.value = window.devicePixelRatio || 1;
});

watch(showControls, async (visible) => {
  controlsWindowVisible.value = visible;
  if (!visible) return;
  await nextTick();
  scheduleControlsWindowSync();
});

watch(
  () => [
    modelRect.value.left,
    modelRect.value.top,
    modelRect.value.right,
    modelRect.value.bottom,
    windowLeft.value,
    windowTop.value,
    windowScale.value,
  ],
  () => {
    scheduleChatWindowSync();
    scheduleControlsWindowSync();
  }
);

watch([controlSize, viewportWidth, viewportHeight], () => {
  scheduleControlsWindowSync();
});

watch(controlsVisible, async (visible) => {
  if (!visible) return;
  await nextTick();
  scheduleControlsBoundsSync();
});

watch([shouldFadeOnModel, shouldIgnoreCursor], async () => {
  if (!hasCursorState.value) {
    hoverFaded.value = false;
    if (clickThroughApplied.value) {
      const result = await setClickThrough(false);
      if (result) {
        windowBehavior.value = result;
        clickThroughApplied.value = result.clickThrough;
      } else {
        clickThroughApplied.value = false;
      }
    }
    return;
  }
  hoverFaded.value = shouldFadeOnModel.value;
  const nextIgnore = shouldIgnoreCursor.value;
  if (clickThroughApplied.value === nextIgnore) return;
  const result = await setClickThrough(nextIgnore);
  if (result) {
    windowBehavior.value = result;
    clickThroughApplied.value = result.clickThrough;
  } else {
    clickThroughApplied.value = nextIgnore;
  }
});

watch(
  [
    hasCursorState,
    shouldFadeOnModel,
    stageViewControlsEnabled,
    controlsHovering,
    sessionsOpen,
  ],
  ([cursorReady, onModel, viewEnabled, hoveringControls, sessionsVisible]) => {
    if (!cursorReady || onModel || viewEnabled || hoveringControls || sessionsVisible) {
      controlsVisible.value = true;
      if (controlsHideTimer) {
        window.clearTimeout(controlsHideTimer);
        controlsHideTimer = null;
      }
      return;
    }
    if (controlsHideTimer) {
      window.clearTimeout(controlsHideTimer);
    }
    controlsHideTimer = window.setTimeout(() => {
      if (
        !shouldFadeOnModel.value &&
        !stageViewControlsEnabled.value &&
        !controlsHovering.value &&
        !sessionsOpen.value
      ) {
        controlsVisible.value = false;
      }
    }, 500);
  },
  { immediate: true }
);
</script>

<template>
  <div class="desktop-root relative h-full w-full">
    <div
      ref="stageContainerRef"
      class="desktop-stage relative z-10 h-full w-full"
      :class="{ 'is-faded': hoverFaded }"
      :style="{ '--hover-fade-opacity': hoverFadeOpacity }"
    >
      <StageViewport
        ref="stageViewportRef"
        :paused="false"
        :focus-at="focusAt"
        :x-offset="stageXOffset"
        :y-offset="stageYOffset"
        :scale="scale"
      />
    </div>
    <div
      v-show="controlsVisible"
      data-controls-hitbox
      class="pointer-events-auto absolute z-30 flex flex-col items-center gap-2"
      :style="controlsPositionStyle"
    >
      <button
        type="button"
        class="rounded-full border border-white/60 bg-white/70 text-neutral-500 shadow-lg backdrop-blur-md transition hover:text-neutral-900"
        :style="{ width: `${controlSize}px`, height: `${controlSize}px` }"
        title="Sessions"
        @click="handleToggleSessions"
      >
        <div
          class="i-solar:chat-round-line-bold mx-auto"
          :style="{ width: `${Math.round(controlSize * 0.5)}px`, height: `${Math.round(controlSize * 0.5)}px` }"
        ></div>
      </button>
      <button
        type="button"
        class="rounded-full border border-white/60 bg-white/70 text-neutral-500 shadow-lg backdrop-blur-md transition hover:text-neutral-900"
        :style="{ width: `${controlSize}px`, height: `${controlSize}px` }"
        title="Settings"
        @click="handleOpenSettings"
      >
        <div
          class="i-solar:settings-outline mx-auto"
          :style="{ width: `${Math.round(controlSize * 0.5)}px`, height: `${Math.round(controlSize * 0.5)}px` }"
        ></div>
      </button>
      <button
        type="button"
        class="rounded-full border border-white/60 bg-white/70 text-neutral-500 shadow-lg backdrop-blur-md transition hover:text-neutral-900"
        :style="{ width: `${controlSize}px`, height: `${controlSize}px` }"
        title="View Controls"
        @click="handleToggleViewControls"
      >
        <div
          class="i-solar:tuning-outline mx-auto"
          :style="{ width: `${Math.round(controlSize * 0.5)}px`, height: `${Math.round(controlSize * 0.5)}px` }"
        ></div>
      </button>
    </div>
    <StageViewOverlay />
    <DesktopSessionPanel :style="sessionsPanelStyle" />
  </div>
</template>
