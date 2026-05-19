# Deploy Seguro SoundGrabber

Este documento cobre o deploy residencial atras da Cloudflare. O objetivo e falhar fechado antes de publicar.

## 1. Predeploy obrigatorio

Rode no servidor, no clone limpo:

```bash
bash scripts/predeploy-check.sh
```

O script bloqueia deploy quando:

- o worktree tem alteracoes locais ou arquivos nao rastreados;
- artefatos sensiveis ainda estao rastreados pelo Git;
- `.env` esta ausente, com placeholders ou `DEV_MODE=true`;
- Redis nao tem senha no `REDIS_URL`;
- `docker-compose.yml` expoe Redis ou API fora de `127.0.0.1`;
- `pip-audit -r requirements.txt` reporta vulnerabilidade;
- testes de seguranca/deploy falham;
- as confirmacoes externas de Cloudflare/origem/backup/monitoramento nao estao marcadas.

## 2. `.env` de producao

Gere valores novos, nao reaproveite valores locais:

```bash
openssl rand -base64 32  # REDIS_PASSWORD
openssl rand -base64 48  # ADMIN_SESSION_SECRET
openssl rand -base64 24  # ADMIN_PASSWORD, ou use senha longa de gerenciador
```

Obrigatorio:

```env
DEV_MODE=false
REDIS_PASSWORD=<novo>
REDIS_URL=redis://:<novo>@redis:6379/0
ADMIN_PASSWORD=<novo, 16+ chars>
ADMIN_SESSION_SECRET=<novo, 32+ chars>
ORIGIN_LOCKDOWN_ENABLED=true
CLOUDFLARE_ACCESS_YONKOU_ENABLED=true
SECRETS_ROTATED_AFTER_AUDIT=true
MONITORING_ENABLED=true
BACKUP_ENCRYPTED_OFF_GIT=true
```

Marque as flags `true` somente depois de validar cada item fora do codigo.

## 3. Cloudflare

Minimo recomendado:

- DNS proxied, TLS `Full (strict)`, Always Use HTTPS e HSTS.
- Cloudflare Tunnel ou reverse proxy local apontando para `http://127.0.0.1:8000`.
- Cloudflare Access em `/yonkou*` com identidade permitida apenas para operador.
- WAF rule para bloquear metodos fora de `GET, POST, PATCH, HEAD, OPTIONS`.
- Rate limiting por rota: `/jobs`, `/analyze`, `/files/*`, `/yonkou/login`.
- Managed WAF rules e Bot Fight Mode/Super Bot Fight Mode.
- Cache rule para `/static/*`; bypass para `/jobs*`, `/files*`, `/analyze`, `/featured`, `/yonkou*`.

Valide origem fechada de fora da rede:

```bash
nmap -Pn <ip-publico> -p 22,80,443,8000,6379
```

Esperado: `8000` e `6379` fechadas. O acesso publico deve passar apenas pela Cloudflare.

## 4. Ubuntu/notebook

Firewall:

```bash
sudo ufw status verbose
sudo iptables -S DOCKER-USER
```

Servicos:

```bash
docker compose ps
docker compose logs --since=30m api worker
bash scripts/ops-check.sh
```

O Redis nao deve ter `ports:` no compose e nao deve responder pela rede externa.

## 5. Monitoramento

Use `scripts/ops-check.sh` em cron/systemd timer. Exemplo simples:

```bash
*/5 * * * * cd /home/glow/soundgrabber && bash scripts/ops-check.sh >> /var/log/soundgrabber-ops.log 2>&1
```

Alertas que exigem acao:

- fila `celery` crescendo;
- `/tmp` ou `/` acima de 80%;
- container reiniciando;
- erros `Traceback`, `OOM`, `no space`, `timeout`;
- CPU sustentada alta durante abuso de upload/download.

## 6. Backup

Backup permitido: somente `.data` se voce precisar preservar Som da Semana/historico local.

```bash
tar -czf - .data | age -r <sua-chave-publica-age> > soundgrabber-data-$(date +%F).tar.gz.age
```

Nunca inclua `.env`, cookies, Redis dump, logs, `.codex`, `.claude` ou backups descriptografados no Git.
