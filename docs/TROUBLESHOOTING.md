# Troubleshooting

Formato do log: `[dd/mm/aaaa hh:mm:ss] NÍVEL: mensagem` em `/var/log/monitor-mailcow.log`.

```bash
sudo grep -E "ERROR|WARNING" /var/log/monitor-mailcow.log | tail -20
```

## Mensagens de log

### Fluxo normal (INFO)

| Mensagem | Significado |
|---|---|
| `Daemon v... iniciado` | Serviço subiu |
| `Iniciando verificação do Mailcow...` | Início de um ciclo |
| `Sistema atualizado.` | Nada pendente |
| `Nova versão pendente: X.` | Atualização detectada; alerta será enviado |
| `Alerta entregue em todos os canais.` | Alerta concluído |
| `Versão já notificada. Aguardando atualização.` | Alerta já enviado; aguardando você aplicar |
| `Atualização confirmada: A -> B.` | Conclusão detectada |
| `Aviso de conclusão entregue em todos os canais.` | Ciclo fechado |
| `Estado legado migrado ...` | Migração da 1.0.0 |
| `Telegram desabilitado (...)` | Sem token/chat ID; ignorado |

### Problemas

| Mensagem | Causa provável | Solução |
|---|---|---|
| `Saída inesperada do update.sh --check (rc=...)` | `MAILCOW_DIR` errado, `update.sh` ausente/sem permissão, ou o Mailcow mudou a mensagem | Rode `./update.sh --check` no diretório e confira a saída; corrija `MAILCOW_DIR` |
| `Falha ao executar update.sh --check: ...` | Caminho inexistente ou timeout (300 s) | Confira o caminho e a conectividade com o GitHub |
| `Não foi possível obter a versão local` | `MAILCOW_DIR` não é clone git, ou erro de propriedade (`dubious ownership`) | Rode `git describe --tags` como root no diretório; se preciso, `git config --global --add safe.directory <dir>` |
| `Erro API GitHub: ...` | Sem internet, DNS, proxy ou limite de requisições | Tentará de novo no próximo ciclo |
| `Versão nova indisponível via GitHub` | A API não retornou a release | Idem |
| `Falha de conexão SMTP: ...` | Host/porta/credenciais incorretos, firewall ou TLS | Teste com `openssl s_client -starttls smtp -connect host:587` |
| `Erro ao enviar para x@y: ...` | Destinatário recusado pelo servidor | Verifique o endereço e as políticas do SMTP |
| `Nenhum destinatário de e-mail configurado.` | `RECIPIENT_EMAILS` vazio | Preencha no `.conf` |
| `Telegram ... falhou (HTTP 400 ... chat not found)` | O destinatário nunca iniciou o bot | Abrir o bot e enviar `/start` |
| `Telegram ... falhou (HTTP 401)` | Token inválido | Gere/copie o token no BotFather |
| `Telegram ... falhou (HTTP 403)` | Bot bloqueado ou removido do grupo | Desbloqueie ou readicione o bot |
| `Estado ilegível (...); recomeçando do zero.` | `estado.json` corrompido | Pode causar reenvio de um alerta; é seguro |
| `Erro ao salvar estado` | Sem permissão ou disco cheio em `/var/lib/monitor-mailcow` | Corrija permissões/espaço |
| `Erro inesperado no ciclo` (com traceback) | Bug | Abra uma issue com o trecho do log |

## O serviço não sobe

```bash
sudo systemctl status mailcow-monitor
sudo journalctl -u mailcow-monitor -n 50 --no-pager
```

* `ERRO FATAL: [SMTP] SMTP_SERVER ausente...` (saída 78): complete o `.conf`. O systemd não tenta reiniciar nesse caso; depois de corrigir, rode `systemctl restart`.
* `... não encontrada`: o `.conf` foi removido; reinstale o pacote ou recrie o arquivo.

## "Não recebi o aviso de conclusão"

1. Rodou o `update.sh` até o fim? Confirme com `./update.sh --check` → `No updates available.`
2. Existe estado pendente? `cat /var/lib/monitor-mailcow/estado.json`
3. Aguarde até `INTERVALO_PENDENTE_MINUTOS`. Acompanhe o log.
4. `concluido.aviso` mostra qual canal ainda falhou; veja o erro correspondente no log.
5. Se a versão local aparecer como `Desconhecida`, o aviso só sai quando ela puder ser lida.

## "Recebi o alerta de novo"

* Houve falha em um canal e o reenvio foi só dele.
* O estado foi apagado ou corrompido.
* Saiu uma nova release enquanto a anterior ainda estava pendente.

## "Não recebi alerta de uma atualização nova"

* Confirme `./update.sh --check` manualmente.
* Veja se o log mostra `Saída inesperada` ou `Erro API GitHub`.
* Verifique se o serviço está ativo.
* Com a versão já notificada, o log mostra `Versão já notificada`.

## E-mails caindo no spam

Use um remetente em domínio com SPF, DKIM e DMARC corretos, preferencialmente fora do Mailcow monitorado.
