# Segurança

## Modelo de ameaças

| Ativo | Risco | Mitigação |
|---|---|---|
| Senha SMTP e token do Telegram | Vazamento por leitura do `.conf` | Modo 600, dono root; evite copiar o arquivo; use conta SMTP exclusiva de envio |
| Execução do `update.sh` como root | Escalada de privilégio se outro usuário puder alterar o script ou o diretório | `MAILCOW_DIR` e `update.sh` graváveis só por root |
| Conteúdo vindo do GitHub (changelog) | Injeção de HTML no e-mail | `html.escape` em todo conteúdo externo; Telegram em modo HTML com escape |
| Estado em disco | Adulteração para suprimir alertas | `/var/lib/monitor-mailcow` modo 700, arquivo 600 |
| Logs | Exposição do token do Telegram | Token mascarado (`***`) nas mensagens de erro; log em modo 640 |
| Integridade do pacote | Pacote adulterado | Confira o `SHA256SUMS` da release |
| Canais de alerta | Informação da infraestrutura em e-mail/Telegram | Versões e changelog públicos; restrinja os destinatários |

## Por que o serviço roda como root

O `update.sh` do Mailcow lê o `mailcow.conf` (acesso restrito) e usa o Docker. Um usuário comum tende a falhar no `--check`. Em vez de reduzir o usuário, o serviço é confinado:

```ini
NoNewPrivileges=yes
PrivateTmp=yes
ProtectHome=yes
ProtectSystem=full
ProtectKernelTunables=yes
ProtectControlGroups=yes
```

`ProtectSystem=full` mantém `/usr`, `/boot` e `/etc` somente leitura para o processo. O estado fica em `/var/lib` e o log em `/var/log`, que seguem graváveis. O Python roda com `-I` (modo isolado), sem carregar código do diretório de trabalho nem de variáveis `PYTHON*`.

## Permissões esperadas

| Caminho | Modo | Dono |
|---|---|---|
| `/etc/mailcow-monitor/mailcow-monitor.conf` | 600 | root |
| `/var/lib/monitor-mailcow/` | 700 | root |
| `/var/lib/monitor-mailcow/estado.json` | 600 | root |
| `/var/log/monitor-mailcow.log` | 640 | root |
| `/opt/monitor-mailcow/monitor_mailcow.py` | 755 | root |

Verificação:

```bash
sudo stat -c '%a %U %n' /etc/mailcow-monitor/mailcow-monitor.conf \
  /var/lib/monitor-mailcow /var/lib/monitor-mailcow/estado.json \
  /var/log/monitor-mailcow.log /opt/monitor-mailcow/monitor_mailcow.py
```

## Rede

Conexões de saída apenas, todas com timeout de 30 s e validação de certificado TLS:

* `https://api.github.com` (release e changelog)
* SMTP configurado (SSL na 465, STARTTLS nas demais)
* `https://api.telegram.org`

Não há porta de escuta.

## Boas práticas

* Use credenciais SMTP exclusivas, com permissão apenas de envio.
* Prefira um SMTP **fora** do Mailcow monitorado.
* Revogue o token do Telegram no BotFather (`/revoke`) se houver suspeita de vazamento.
* Monitore o serviço por fora (se ele parar, ninguém é avisado).
* Valide o `SHA256SUMS` antes de instalar.
* Revise o código antes de instalar em produção; ele é um único arquivo.

## Reportar vulnerabilidades

Abra uma issue **sem detalhes sensíveis** pedindo um canal privado, ou use o aviso privado de segurança do GitHub (aba *Security*), se estiver habilitado no repositório.
