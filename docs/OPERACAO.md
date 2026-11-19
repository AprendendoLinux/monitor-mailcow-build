# Operação

## Instalação

```bash
sha256sum -c SHA256SUMS                      # confira o pacote baixado
sudo dpkg -i monitor-mailcow_1.1.2_all.deb
sudo nano /etc/mailcow-monitor/mailcow-monitor.conf
sudo systemctl restart mailcow-monitor
```

O `postinst` cria `/var/lib/monitor-mailcow` (700), ajusta o `.conf` para 600 e o log para 640, e habilita e reinicia o serviço.

> Se `python3` ou `git` não estiverem instalados, rode `sudo apt -f install` depois do `dpkg -i`.

## Atualização do pacote

Instale o novo `.deb` por cima:

```bash
sudo dpkg -i monitor-mailcow_<versão>_all.deb
```

Automaticamente:

* O `.conf` é mantido (é um *conffile*). Opções novas são opcionais, com padrão.
* O estado antigo (`ultima_versao_avisada.txt`, da 1.0.0) é migrado para `estado.json` no primeiro ciclo, sem reenviar alertas. Veja [ARQUITETURA.md](ARQUITETURA.md#migração-do-estado-da-100).
* Serviço, logrotate e permissões são substituídos e o serviço reinicia.

Confira:

```bash
sudo systemctl status mailcow-monitor
sudo tail -n 20 /var/log/monitor-mailcow.log   # "Daemon v<versão> iniciado"
```

Se o dpkg perguntar sobre o `.conf`, mantenha a **sua** versão (`N`).

## Operação diária

```bash
sudo systemctl status mailcow-monitor           # status
sudo systemctl restart mailcow-monitor          # aplicar mudanças no .conf
sudo tail -f /var/log/monitor-mailcow.log       # log em tempo real
sudo cat /var/lib/monitor-mailcow/estado.json   # estado atual
sudo journalctl -u mailcow-monitor -n 50        # erros de inicialização
```

### Fluxo ao receber um alerta

1. Receba o alerta (e-mail e Telegram).
2. Aplique a atualização no servidor: `cd /caminho/do/mailcow && ./update.sh`.
3. Em até `INTERVALO_PENDENTE_MINUTOS` (padrão 15 min) o aviso de **conclusão** sai para os mesmos destinatários.

### Reenviar o alerta da versão pendente

```bash
sudo rm /var/lib/monitor-mailcow/estado.json
sudo systemctl restart mailcow-monitor
```

### Adicionar ou remover destinatários

Edite `RECIPIENT_EMAILS` / `TELEGRAM_CHAT_ID` e reinicie o serviço.

## Testes

### Verificar a detecção

```bash
cd /caminho/do/mailcow && ./update.sh --check
```

A saída deve conter `Updated code is available.` ou `No updates available.`. Caso contrário o daemon fica em `indeterminado`.

### Testar o envio de e-mail sem afetar o estado

Envia o e-mail de conclusão só para um endereço de teste, usando o SMTP configurado. Não toca no `estado.json` nem no Telegram:

```bash
sudo MAILCOW_MONITOR_LOG=/tmp/teste.log python3 -I - <<'EOF'
import sys
sys.path.insert(0, "/opt/monitor-mailcow")
import monitor_mailcow as m
m.CFG["recipients"] = "seu-email@exemplo.com"
corpo = m.html_concluido("2026-10", "2026-11", "2026-11-19T10:00:00-03:00",
                         "2026-11-19T14:00:00-03:00", "Changelog de teste")
print("enviado:", m.enviar_email("[TESTE] Mailcow atualizado", corpo))
EOF
```

Troque `html_concluido(...)` por `html_alerta("2026-10", "2026-11", "notas")` para testar o alerta crítico. Para testar o Telegram: `m.enviar_telegram(m.tg_concluido("2026-10", "2026-11", "2026-11-19T10:00:00-03:00", "2026-11-19T14:00:00-03:00"))`.

### Teste completo de ponta a ponta

Só é possível aplicando uma atualização real do Mailcow: aguarde o alerta, rode o `update.sh` e verifique o aviso de conclusão.

## Backup

Basta guardar `/etc/mailcow-monitor/mailcow-monitor.conf`. O estado é reconstruível (no pior caso, um alerta é reenviado).

## Desinstalação

```bash
sudo dpkg -r monitor-mailcow      # remove, mantém .conf, estado e log
sudo dpkg -P monitor-mailcow      # purge: remove também .conf, estado, log e /opt/monitor-mailcow
```

## Saúde do daemon

O daemon não tem monitoramento próprio. Se ele parar de rodar, ninguém é avisado. Sugestão: monitore `systemctl is-active mailcow-monitor` por fora (Zabbix, Uptime Kuma, cron etc.).
