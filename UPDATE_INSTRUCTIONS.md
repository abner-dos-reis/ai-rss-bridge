# 🔄 Atualização - Anti-Bot Protection

## O que foi adicionado

✅ **Cloudscraper** - Bypass automático de Cloudflare e proteções anti-bot
✅ **Múltiplas estratégias de fetch** - Tenta 4 métodos diferentes
✅ **Headers HTTP realistas** - Imita navegador Chrome real
✅ **Retry logic melhorado** - 3 tentativas com backoff
✅ **Timeouts aumentados** - 60s para AI, 15-20s para fetching

## Como atualizar

### Opção 1: Rebuild completo (Recomendado)

```bash
# Parar containers
docker-compose down

# Rebuild com as novas dependências
docker-compose up --build -d

# Verificar logs
docker-compose logs -f backend
```

### Opção 2: Update sem rebuild

```bash
# Instalar cloudscraper no container existente
docker exec -it ai-rss-backend pip install cloudscraper

# Reiniciar
docker-compose restart backend
```

## Verificar instalação

```bash
# Ver se cloudscraper está instalado
docker exec -it ai-rss-backend pip list | grep cloudscraper

# Ver logs de inicialização
docker-compose logs backend | grep cloudscraper
```

Você deve ver:
```
✓ cloudscraper available - can bypass Cloudflare protection
```

## Testar

Agora tente gerar feeds de sites que antes bloqueavam:
- Sites com Cloudflare
- Sites com proteção anti-bot
- Sites que retornavam 403 Forbidden

## Limitações

Alguns sites ainda podem bloquear:
- **DeepLearning.AI** - Proteção muito forte, use feed oficial se disponível
- Sites que requerem JavaScript pesado
- Sites com autenticação obrigatória

Para esses casos, veja `ANTI_BOT_PROTECTION.md` para alternativas.

## Rollback

Se houver problemas, voltar para versão anterior:

```bash
git checkout main
docker-compose up --build -d
```
