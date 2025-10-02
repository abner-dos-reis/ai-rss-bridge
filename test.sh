#!/bin/bash
echo "🔧 Testando aplicação AI RSS Bridge..."

# Verificar se existe docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose não encontrado"
    exit 1
fi

# Verificar arquivos essenciais
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml não encontrado"
    exit 1
fi

if [ ! -f "backend/Dockerfile" ]; then
    echo "❌ backend/Dockerfile não encontrado"
    exit 1
fi

if [ ! -f "frontend/Dockerfile" ]; then
    echo "❌ frontend/Dockerfile não encontrado"
    exit 1
fi

echo "✅ Todos os arquivos necessários encontrados"
echo ""
echo "Para rodar a aplicação:"
echo "  docker-compose up --build"
echo ""
echo "Depois acesse: http://127.0.0.1:8895"