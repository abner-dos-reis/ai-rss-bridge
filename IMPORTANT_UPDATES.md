# ⚠️ IMPORTANTE - Como Atualizar Sem Perder Configurações

## 🔐 Suas configurações são salvas em `/data`

As chaves de API, feeds e configurações ficam salvos em:
- `./data/config.json` (chaves de API criptografadas)
- `./data/encryption.key` (chave de criptografia)
- `./data/feeds.db` (banco de dados dos feeds)

## ✅ COMANDOS CORRETOS (mantém configurações)

### Para atualizar o código:
```bash
# Parar containers
docker-compose stop

# Rebuild e iniciar
docker-compose up --build -d
```

### Para reiniciar:
```bash
docker-compose restart backend
```

### Para ver logs:
```bash
docker-compose logs -f backend
```

## ❌ NUNCA USE (apaga suas configurações):

```bash
# ❌ Isso apaga TUDO incluindo API keys
docker-compose down -v

# ❌ Isso remove o diretório data
rm -rf data/
```

## 🔄 Se acidentalmente apagou as configurações:

1. Vá para a aba **Config** na interface
2. Adicione suas chaves de API novamente
3. Elas serão salvas automaticamente em `./data/config.json`

## 📂 Backup das configurações:

```bash
# Fazer backup
cp -r data data_backup

# Restaurar backup
cp -r data_backup/* data/
```

## 🐛 Problemas?

Se as configurações não estão sendo salvas:
1. Verifique se o diretório `./data` existe
2. Verifique permissões: `ls -la data/`
3. Veja os logs: `docker-compose logs backend | grep ConfigManager`
