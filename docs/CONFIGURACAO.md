# Configuração

Arquivo: `/etc/mailcow-monitor/mailcow-monitor.conf` (formato INI, modo 600, dono root).
Depois de editar: `sudo systemctl restart mailcow-monitor`.

Valores podem usar aspas simples ou duplas; elas são removidas.

## Exemplo completo

```ini
[GERAL]
MAILCOW_DIR = /opt/mailcow-dockerized
INTERVALO_HORAS = 12
# INTERVALO_PENDENTE_MINUTOS = 15

[SMTP]
SMTP_SERVER = smtp.seuprovedor.com
SMTP_PORT = 465
SMTP_USER = alertas@dominio.com.br
SMTP_PASS = sua-senha-segura
SENDER_NAME = Monitor Mailcow
SENDER_EMAIL = alertas@dominio.com.br
RECIPIENT_EMAILS = admin@dominio.com.br, ti@dominio.com.br

[TELEGRAM]
TELEGRAM_BOT_TOKEN = 1234567890:ABCdefGhIjkLmnopQRstUvwxYz
TELEGRAM_CHAT_ID = 11111111, 22222222
```

## Referência das opções

### `[GERAL]`

| Chave | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `MAILCOW_DIR` | não | `/opt/mailcow-dockerized` | Diretório do Mailcow (clone git com o `update.sh`). Ajuste se instalou em outro caminho, por exemplo `/srv/mailcow-dockerized`. |
| `INTERVALO_HORAS` | não | `12` | Intervalo entre verificações quando não há atualização pendente. Mínimo 1. |
| `INTERVALO_PENDENTE_MINUTOS` | não | `15` | Intervalo entre verificações enquanto há atualização pendente. Define em quanto tempo o aviso de conclusão sai após o `update.sh`. Mínimo 1. |

### `[SMTP]`

| Chave | Obrigatória | Descrição |
|---|---|---|
| `SMTP_SERVER` | sim | Host do servidor SMTP. |
| `SMTP_PORT` | não (465) | **465** usa SSL direto. Qualquer outra porta (587, 25) usa STARTTLS. O certificado é validado. |
| `SMTP_USER` / `SMTP_PASS` | sim | Credenciais de autenticação. |
| `SENDER_NAME` / `SENDER_EMAIL` | sim | Remetente exibido e endereço de envelope. |
| `RECIPIENT_EMAILS` | sim | Destinatários separados por vírgula. Cada um recebe uma mensagem individual (sem expor os demais). |

Recomendação: use um servidor SMTP **externo ao Mailcow** monitorado. Se o Mailcow estiver fora do ar ou com a fila comprometida, o alerta ainda sai.

### `[TELEGRAM]`

| Chave | Obrigatória | Descrição |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | não | Token do bot. Vazio desativa o Telegram. O prefixo `bot` é aceito e removido. |
| `TELEGRAM_CHAT_ID` | não | Um ou mais IDs separados por vírgula (usuários ou grupos). Vazio desativa o Telegram. |

#### Como configurar o Telegram

1. No Telegram, converse com o `@BotFather`, envie `/newbot` e guarde o **token**.
2. Cada destinatário deve abrir o bot e enviar `/start`. Sem isso a API responde `400 chat not found`.
3. Para descobrir o seu chat ID, envie uma mensagem ao bot e abra
   `https://api.telegram.org/bot<TOKEN>/getUpdates`; o ID está em `message.chat.id`.
   Em grupos o ID é negativo; adicione o bot ao grupo antes.

## Validação da configuração

* Chave obrigatória ausente ou número inválido: o daemon escreve o erro em stderr (visível em `journalctl -u mailcow-monitor`) e sai com **código 78**. O systemd **não** reinicia nesse caso, evitando loop.
* Arquivo `.conf` inexistente: mesmo comportamento.
* Para testar sem esperar o ciclo: veja [OPERACAO.md](OPERACAO.md#testes).

## Variáveis de ambiente (desenvolvimento e testes)

| Variável | Padrão | Uso |
|---|---|---|
| `MAILCOW_MONITOR_CONF` | `/etc/mailcow-monitor/mailcow-monitor.conf` | Caminho alternativo do `.conf` |
| `MAILCOW_MONITOR_STATE_DIR` | `/var/lib/monitor-mailcow` | Diretório do `estado.json` |
| `MAILCOW_MONITOR_LOG` | `/var/log/monitor-mailcow.log` | Arquivo de log |

Não são necessárias em produção.
