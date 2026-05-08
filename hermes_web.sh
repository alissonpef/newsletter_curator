#!/bin/bash

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON_EXEC="${PROJECT_ROOT}/.venv/bin/python3"
WEB_MODULE="hermes.main"

export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/nvidia:$LD_LIBRARY_PATH"
export PATH="/usr/local/cuda/bin:$PATH"

function check_ollama() {
    if ! command -v ollama > /dev/null 2>&1; then
        echo "❌ Erro: Comando 'ollama' não encontrado no PATH."
        return 1
    fi

    if ! pgrep -x "ollama" > /dev/null; then
        echo "⚠️ Ollama não detectado. Tentando iniciar..."
        ollama serve > /tmp/ollama_web.log 2>&1 &
        
        local count=0
        while ! curl -s http://localhost:11434/api/tags > /dev/null; do
            if [ $count -gt 15 ]; then
                echo "❌ Falha ao iniciar o Ollama."
                return 1
            fi
            echo "⌛ Aguardando Ollama ($count/15)..."
            sleep 1
            ((count++))
        done
        echo "✅ Ollama iniciado."
    else
        echo "✅ Ollama já está em execução."
    fi
    return 0
}


cd "$PROJECT_ROOT"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

check_ollama || exit 1

export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH}"

echo "🚀 Iniciando Hermes Web Server..."
echo "📍 Dashboard: http://127.0.0.1:8787 (ou na porta configurada no .env)"

"$PYTHON_EXEC" -m "$WEB_MODULE"
