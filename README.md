# 🛡️ Monitor Crítico de Atualizações - Mailcow

![versão](https://img.shields.io/badge/versão-1.1.1-blue)

Daemon para Debian/Ubuntu, escrito em Python (somente biblioteca padrão), que monitora o [Mailcow Dockerized](https://mailcow.email/) e avisa a equipe por **E-mail (HTML)** e **Telegram**:

1. quando existe uma atualização pendente (alerta crítico);
2. quando a atualização é aplicada (aviso de conclusão, com o tempo de exposição).

## ✨ Funcionalidades

* **Detecção:** executa `./update.sh --check` no diretório do Mailcow e consulta a API de releases do GitHub para obter a versão e o changelog.
* **Alerta crítico:** e-mail HTML e mensagem no Telegram com versão atual, nova versão e changelog.
* **Aviso de conclusão:** depois que você roda o `update.sh`, o daemon confirma a nova versão e envia um e-mail (mesmo padrão visual, em verde) e uma mensagem no Telegram para os mesmos destinatários.
* **Estado por canal:** se o e-mail falhar e o Telegram não, apenas o canal com falha é reenviado no próximo ciclo.
* **Sem repetição:** cada versão gera um único alerta e um único aviso de conclusão.
* **Ciclo adaptativo:** verifica a cada `INTERVALO_HORAS` (padrão 12h). Enquanto há uma atualização pendente, verifica a cada `INTERVALO_PENDENTE_MINUTOS` (padrão 15 min), para que o aviso de conclusão saia logo após o update.
* **Seguro por padrão:** conteúdo vindo do GitHub é escapado no HTML, há timeout em todas as chamadas de rede e subprocessos, o token do Telegram é mascarado nos logs e o serviço roda com hardening do systemd.
* **Pacote `.deb`** com systemd e logrotate.

## 🔄 Como funciona

```
update.sh --check ──► "Updated code is available."
        │
        ▼
 consulta GitHub ─► envia ALERTA (e-mail + Telegram) ─► estado: pendente
        │
        ▼  (você roda ./update.sh no Mailcow)
 update.sh --check ──► "No updates available" + versão local conhecida
        │
        ▼
 envia AVISO DE CONCLUSÃO (e-mail + Telegram) ─► estado: limpo
```

A atualização é considerada concluída quando o `--check` informa `No updates available` (ou a versão local, via `git describe --tags`, é igual à versão pendente) **e** a versão local pôde ser lida. Se a saída do `--check` for inesperada ou a versão local for desconhecida, nada é enviado e o erro vai para o log.

> O daemon não repete o alerta enquanto a atualização não é aplicada. Ele só reenvia se algum canal tiver falhado.

## 📂 Estrutura no sistema

| Caminho | Função |
|---|---|
| `/opt/monitor-mailcow/monitor_mailcow.py` | Código do daemon |
| `/etc/mailcow-monitor/mailcow-monitor.conf` | Configuração (modo 600, preservada em atualizações) |
| `/var/lib/monitor-mailcow/estado.json` | Estado persistente (versão pendente e canais já avisados) |
| `/etc/systemd/system/mailcow-monitor.service` | Serviço systemd |
| `/etc/logrotate.d/monitor-mailcow` | Rotação de logs (diária, 7 arquivos) |
| `/var/log/monitor-mailcow.log` | Log (modo 640) |

## 🚀 Instalação

Baixe o `.deb` na aba Releases e instale:

```bash
sudo dpkg -i monitor-mailcow.deb
```

As dependências são `python3` e `git`. Depois, edite a configuração e reinicie o serviço.

## ⬆️ Atualização de uma versão anterior

Basta instalar o novo pacote por cima:

```bash
sudo dpkg -i monitor-mailcow.deb
```

O que acontece automaticamente:

* **Sua configuração é mantida.** O dpkg não sobrescreve o `.conf` modificado. As opções novas são opcionais e têm valor padrão, então não é necessário editar nada.
* **Estado migrado.** O arquivo antigo `/opt/monitor-mailcow/ultima_versao_avisada.txt` é lido no primeiro ciclo e convertido para `estado.json`. Uma atualização que já tinha sido avisada e continua pendente **não é reavisada**, e quando você aplicá-la o aviso de conclusão será enviado. O arquivo antigo é renomeado para `.migrado`.
* **Serviço, logrotate e permissões** são substituídos e o serviço é reiniciado.

Para conferir:

```bash
sudo systemctl status mailcow-monitor
sudo tail -n 20 /var/log/monitor-mailcow.log   # deve mostrar "Daemon v1.1.1 iniciado"
```

## ⚙️ Configuração

Arquivo: `/etc/mailcow-monitor/mailcow-monitor.conf`

```ini
[GERAL]
MAILCOW_DIR = /opt/mailcow-dockerized
# Intervalo (horas) entre verificações quando não há atualização pendente
INTERVALO_HORAS = 12
# Opcional (padrão 15): intervalo (minutos) enquanto há atualização pendente
# INTERVALO_PENDENTE_MINUTOS = 15

[SMTP]
SMTP_SERVER = smtp.seuprovedor.com
# 465 = SSL; qualquer outra porta usa STARTTLS
SMTP_PORT = 465
SMTP_USER = alertas@dominio.com.br
SMTP_PASS = sua-senha-segura
SENDER_NAME = Monitor Mailcow
SENDER_EMAIL = alertas@dominio.com.br
# Separe por vírgula
RECIPIENT_EMAILS = admin@dominio.com.br, ti@dominio.com.br

[TELEGRAM]
# Deixe vazio para desativar
TELEGRAM_BOT_TOKEN = 1234567890:ABCdefGhIjkLmnopQRstUvwxYz
# Separe por vírgula
TELEGRAM_CHAT_ID = 11111111, 22222222
```

Aplique as mudanças com `sudo systemctl restart mailcow-monitor`.

Se faltar uma chave obrigatória, o daemon registra o erro e **não** fica reiniciando em loop (código de saída 78).

## 🛠️ Operação e troubleshooting

```bash
sudo systemctl status mailcow-monitor      # status
sudo tail -f /var/log/monitor-mailcow.log  # log em tempo real
sudo cat /var/lib/monitor-mailcow/estado.json   # estado atual
```

**Reenviar o alerta de uma versão pendente:**
```bash
sudo rm /var/lib/monitor-mailcow/estado.json
sudo systemctl restart mailcow-monitor
```

**Testar o aviso de conclusão:** depois do alerta, rode o `./update.sh` do Mailcow. Em até `INTERVALO_PENDENTE_MINUTOS` o aviso é enviado.

| Sintoma no log | Causa e solução |
|---|---|
| `Telegram ... falhou (HTTP 400 ... chat not found)` | O dono do chat nunca falou com o bot. Envie `/start` ao bot no Telegram. |
| `Saída inesperada do update.sh --check` | O Mailcow mudou a mensagem do `--check` ou o `MAILCOW_DIR` está errado. Rode `./update.sh --check` manualmente no diretório. |
| `Não foi possível obter a versão local` | `MAILCOW_DIR` não é um clone git ou há problema de permissão no repositório. |
| `Erro API GitHub` | Sem acesso à internet ou limite de requisições. Tenta de novo no próximo ciclo. |
| `Falha de conexão SMTP` | Servidor, porta, usuário ou senha incorretos. |

## 🔒 Segurança

* O `.conf` guarda a senha SMTP e o token do Telegram em texto puro e tem modo 600 (somente root).
* O serviço roda como **root**, porque o `update.sh` do Mailcow lê o `mailcow.conf` (restrito) e usa o Docker. Ele é limitado com `NoNewPrivileges`, `PrivateTmp`, `ProtectHome` e `ProtectSystem=full`.
* O `update.sh` e o `MAILCOW_DIR` só devem ser graváveis por root, já que o daemon executa esse script.
* O changelog vindo do GitHub é escapado antes de entrar no e-mail.

## 📦 Build do pacote

Estrutura do repositório:

```
monitor-mailcow-build/
├── DEBIAN/        control, conffiles, postinst, prerm, postrm
├── etc/           mailcow-monitor/, systemd/system/, logrotate.d/
└── opt/           monitor-mailcow/monitor_mailcow.py
```

Compilação (use `--root-owner-group` para os arquivos pertencerem ao root):

```bash
chmod 755 monitor-mailcow-build/DEBIAN/{postinst,prerm,postrm}
chmod 600 monitor-mailcow-build/etc/mailcow-monitor/mailcow-monitor.conf
dpkg-deb --root-owner-group -Zxz --build monitor-mailcow-build monitor-mailcow.deb
```

Ao alterar o código, atualize `VERSAO_APP` em `monitor_mailcow.py` e `Version` em `DEBIAN/control`.

**Importante:** não altere o `mailcow-monitor.conf` do pacote em novas versões sem necessidade. Como ele é um conffile, qualquer mudança faz o dpkg perguntar ao usuário que já editou o arquivo. Novas opções devem ser opcionais no código, com valor padrão.

## 📜 Changelog

**1.1.1**
* Correção: a migração do estado antigo usa a data real do último alerta no cálculo do tempo de exposição.
* Correção: `estado.json` com modo 600; changelog buscado no GitHub quando o estado migrado não o tem.

**1.1.0**
* Novo: aviso de conclusão por e-mail e Telegram após a atualização.
* Novo: estado em `/var/lib/monitor-mailcow/estado.json`, por canal, com migração automática do arquivo antigo.
* Novo: ciclo curto enquanto há atualização pendente (`INTERVALO_PENDENTE_MINUTOS`).
* Correção: changelog do GitHub escapado no HTML; Telegram agora usa HTML em vez de Markdown.
* Correção: timeouts em rede e subprocessos; falha de e-mail não suprime mais o Telegram nem o contrário.
* Correção: erro de configuração não gera loop de reinício.
* Segurança: hardening do systemd, log com modo 640, token mascarado nos logs.
* Pacote: `postrm` com limpeza no `purge` e arquivos com dono root.

**1.0.0** — Versão inicial.
