#!/bin/bash

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON_EXEC="${PROJECT_ROOT}/.venv/bin/python3"
CLI_MODULE="hermes.cli"

export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/nvidia:$LD_LIBRARY_PATH"
export PATH="/usr/local/cuda/bin:$PATH"

function check_ollama() {
    if ! command -v ollama > /dev/null 2>&1; then
        echo "❌ Erro: Comando 'ollama' não encontrado no PATH."
        echo "Verifique se o Ollama está instalado e acessível."
        return 1
    fi

    if ! pgrep -x "ollama" > /dev/null; then
        echo "⚠️ Ollama não detectado. Tentando iniciar..."
        ollama serve > /tmp/ollama_start.log 2>&1 &
        
        local count=0
        while ! curl -s http://localhost:11434/api/tags > /dev/null; do
            if [ $count -gt 15 ]; then
                echo "❌ Falha ao iniciar o Ollama após 15 segundos."
                echo "Log de erro do Ollama:"
                cat /tmp/ollama_start.log
                return 1
            fi
            echo "⌛ Aguardando Ollama (tentativa $count/15)..."
            sleep 1
            ((count++))
        done
        echo "✅ Ollama iniciado com sucesso."
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

DATE_REF=$1

export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH}"

echo "🚀 Iniciando Hermes Pipeline..."
"$PYTHON_EXEC" -m "$CLI_MODULE" "$DATE_REF"

if [ $? -eq 0 ]; then
    echo "✨ Processo concluído!"
else
    echo "❌ Ocorreu um erro no pipeline."
    exit 1
fi
