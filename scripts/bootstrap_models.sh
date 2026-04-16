#!/usr/bin/env bash
set -euo pipefail

CHAT_MODEL="${OLLAMA_CHAT_MODEL:-qwen3.5:9b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
PIPER_MODEL_PATH="${PIPER_MODEL_PATH:-models/pt_BR-voice.onnx}"
LOCAL_OLLAMA_BIN=".tools/ollama/bin/ollama"

if command -v ollama >/dev/null 2>&1; then
  OLLAMA_BIN="$(command -v ollama)"
elif [[ -x "$LOCAL_OLLAMA_BIN" ]]; then
  OLLAMA_BIN="$LOCAL_OLLAMA_BIN"
else
  echo "ollama command not found in PATH and local binary is missing at $LOCAL_OLLAMA_BIN"
  exit 1
fi

echo "Pulling Ollama chat model: $CHAT_MODEL"
"$OLLAMA_BIN" pull "$CHAT_MODEL"

echo "Pulling Ollama embedding model: $EMBED_MODEL"
"$OLLAMA_BIN" pull "$EMBED_MODEL"

if [[ ! -f "$PIPER_MODEL_PATH" ]]; then
  echo "Piper model not found at $PIPER_MODEL_PATH"
  echo "Download the model and export PIPER_MODEL_PATH if needed."
  exit 1
fi

echo "Model bootstrap complete"
