# 🐛 DEBUG - Como testar se backend está funcionando

## 1. Rodar aplicação com logs:
```bash
docker-compose down
docker-compose up --build --no-cache
```

## 2. Testar manualmente os endpoints:

### Testar se API está rodando:
```bash
curl http://127.0.0.1:8895/api/info
```
**Deve retornar**: JSON com informações da API

### Testar salvar API key:
```bash
curl -X POST http://127.0.0.1:8895/api/config/api-keys \
  -H "Content-Type: application/json" \
  -d '{"provider":"openai","api_key":"test123"}'
```
**Deve retornar**: `{"message":"API key saved for openai"}`

### Testar listar APIs salvas:
```bash
curl http://127.0.0.1:8895/api/config/api-keys
```
**Deve retornar**: `{"saved_providers":["openai"]}`

## 3. Verificar logs no terminal:

Procure por estas mensagens:
- `ConfigManager initialized`
- `=== SAVE API KEY REQUEST ===`
- `Saving API key for provider: openai`
- `API key saved successfully`

## 4. Verificar arquivos criados:

No container ou volume Docker, deve existir:
- `/app/data/config.json` (com as APIs criptografadas)
- `/app/data/encryption.key` (chave de criptografia)

## 5. Frontend - abrir Developer Tools:

1. F12 → Console
2. Tentar salvar API key no Config
3. Verificar mensagens no console:
   - `Saving API key for openai...`
   - `Save API key response: 200 {message: "..."}`
   - `Saved providers response: {saved_providers: [...]}`

## ❗ Se não funcionar:

1. Verificar se porta 8895 está livre
2. Verificar se Docker tem permissões para criar arquivos
3. Verificar se não há erro de CORS
4. Verificar logs do backend no docker-compose