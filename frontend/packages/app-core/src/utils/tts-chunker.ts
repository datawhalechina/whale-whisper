export const TTS_FLUSH_INSTRUCTION = "\u200B";
export const TTS_SPECIAL_TOKEN = "\u2063";

const keptPunctuations = new Set(["?", "？", "!", "！"]);
const hardPunctuations = new Set([
  ".",
  "。",
  "?",
  "？",
  "!",
  "！",
  "…",
  "⋯",
  "～",
  "~",
  "\n",
  "\t",
  "\r",
]);
const softPunctuations = new Set([
  ",",
  "，",
  "、",
  "–",
  "—",
  ":",
  "：",
  ";",
  "；",
  "《",
  "》",
  "「",
  "」",
]);

export type TtsChunkReason = "boost" | "limit" | "hard" | "flush" | "special";

export interface TtsInputChunk {
  text: string;
  words: number;
  reason: TtsChunkReason;
}

export interface TtsInputChunkOptions {
  boost?: number;
  minimumWords?: number;
  maximumWords?: number;
}

type SegmentLike = { segment?: string; isWordLike?: boolean };
type SegmenterLike = { segment: (input: string) => Iterable<SegmentLike> };

function createSegmenter(granularity: "word" | "grapheme"): SegmenterLike | null {
  const SegmenterCtor = (Intl as any)?.Segmenter as
    | (new (locales?: string | string[], options?: { granularity: string }) => SegmenterLike)
    | undefined;
  if (!SegmenterCtor) return null;
  try {
    return new SegmenterCtor(undefined, { granularity });
  } catch {
    return null;
  }
}

function splitGraphemes(text: string, segmenter: SegmenterLike | null) {
  if (!text) return [];
  if (!segmenter) {
    return Array.from(text);
  }
  const units: string[] = [];
  for (const token of segmenter.segment(text)) {
    if (typeof token?.segment === "string" && token.segment.length > 0) {
      units.push(token.segment);
    }
  }
  return units.length > 0 ? units : Array.from(text);
}

function countWordLike(text: string, segmenter: SegmenterLike | null) {
  if (!text) return 0;
  if (!segmenter) {
    const matched = text.match(/[A-Za-z0-9\u4e00-\u9fff]+/g);
    return matched?.length ?? 0;
  }
  let count = 0;
  for (const token of segmenter.segment(text)) {
    if (token?.isWordLike) {
      count += 1;
    }
  }
  return count;
}

export function sanitizeTtsChunk(text: string) {
  return text
    .replaceAll(TTS_SPECIAL_TOKEN, "")
    .replaceAll(TTS_FLUSH_INSTRUCTION, "")
    .trim();
}

export function chunkTtsInput(
  inputText: string,
  options?: TtsInputChunkOptions
): TtsInputChunk[] {
  const { boost = 2, minimumWords = 4, maximumWords = 12 } = options ?? {};
  const source = inputText.trim();
  if (!source) return [];

  const graphemeSegmenter = createSegmenter("grapheme");
  const wordSegmenter = createSegmenter("word");
  const input = splitGraphemes(source, graphemeSegmenter);

  const chunks: TtsInputChunk[] = [];
  let yieldCount = 0;
  let buffer = "";
  let chunk = "";
  let chunkWordsCount = 0;
  let previousValue: string | undefined;
  let index = 0;

  while (index < input.length) {
    let value = input[index];

    if (value.length > 1) {
      previousValue = value;
      index += 1;
      continue;
    }

    const flush = value === TTS_FLUSH_INSTRUCTION;
    const special = value === TTS_SPECIAL_TOKEN;
    const hard = hardPunctuations.has(value);
    const soft = softPunctuations.has(value);
    const kept = keptPunctuations.has(value);
    let consumed = 1;

    if (flush || special || hard || soft) {
      switch (value) {
        case ".":
        case ",": {
          if (previousValue !== undefined && /\d/.test(previousValue)) {
            const nextValue = input[index + 1];
            if (nextValue && /\d/.test(nextValue)) {
              buffer += value;
              previousValue = value;
              index += consumed;
              continue;
            }
          } else if (value === ".") {
            const nextValue = input[index + 1];
            const afterNextValue = input[index + 2];
            if (nextValue === "." && afterNextValue === ".") {
              value = "…";
              consumed = 3;
            }
          }
          break;
        }
      }

      if (buffer.length === 0) {
        if (special) {
          chunks.push({
            text: "",
            words: 0,
            reason: "special",
          });
          yieldCount += 1;
          chunkWordsCount = 0;
        }

        previousValue = value;
        index += consumed;
        continue;
      }

      const words = countWordLike(buffer, wordSegmenter);

      if (chunkWordsCount > minimumWords && chunkWordsCount + words > maximumWords) {
        const text = kept ? `${chunk.trim()}${value}` : chunk.trim();
        chunks.push({
          text,
          words: chunkWordsCount,
          reason: "limit",
        });
        yieldCount += 1;
        chunk = "";
        chunkWordsCount = 0;
      }

      chunk += buffer + value;
      chunkWordsCount += words;
      buffer = "";

      if (special) {
        chunks.push({
          text: chunk.slice(0, -1).trim(),
          words: chunkWordsCount,
          reason: "special",
        });
        yieldCount += 1;
        chunk = "";
        chunkWordsCount = 0;
      } else if (flush || hard || chunkWordsCount > maximumWords || yieldCount < boost) {
        chunks.push({
          text: chunk.trim(),
          words: chunkWordsCount,
          reason: flush ? "flush" : hard ? "hard" : chunkWordsCount > maximumWords ? "limit" : "boost",
        });
        yieldCount += 1;
        chunk = "";
        chunkWordsCount = 0;
      }

      previousValue = value;
      index += consumed;
      continue;
    }

    buffer += value;
    previousValue = value;
    index += 1;
  }

  if (chunk.length > 0 || buffer.length > 0) {
    chunks.push({
      text: (chunk + buffer).trim(),
      words: chunkWordsCount + countWordLike(buffer, wordSegmenter),
      reason: "flush",
    });
  }

  return chunks;
}

export function toSpeakableTtsChunks(
  inputText: string,
  options?: TtsInputChunkOptions
) {
  return chunkTtsInput(inputText, options)
    .map((item) => sanitizeTtsChunk(item.text))
    .filter((text) => text.length > 0);
}
