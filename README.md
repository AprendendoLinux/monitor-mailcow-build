# 🛡️ Monitor Crítico de Atualizações - Mailcow

Um daemon robusto e automatizado para sistemas Debian/Ubuntu, desenvolvido em Python, que monitora implacavelmente o [Mailcow Dockerized](https://mailcow.email/) em busca de atualizações pendentes. 

O objetivo deste projeto é garantir a segurança da infraestrutura: quando uma nova release oficial é detectada no GitHub e validada no servidor local, o sistema dispara alertas "em tom de urgência" via E-mail (HTML estilizado) e Telegram, cobrando a equipe de infraestrutura até que o patch seja aplicado.

## ✨ Funcionalidades

* **Verificação Dupla:** Cruza a saída do script nativo do Mailcow (`./update.sh --check`) com a API pública do repositório no GitHub.
* **Alertas Agressivos:** Envia e-mails em HTML formatados como "Aviso Crítico de Segurança" contendo as versões (Atual vs. Nova) e o *Changelog* completo extraído do GitHub.
* **Integração com Telegram:** Disparo de mensagens diretas para múltiplos IDs de administradores/grupos.
* **Inteligência de Estado:** Cria um arquivo de controle (`ultima_versao_avisada.txt`) para notificar a equipe apenas uma vez a cada nova release, evitando spam excessivo.
* **Empacotamento Nativo (.deb):** Instalável via `dpkg/apt`, garantindo conformidade com o ecossistema Debian.
* **Daemon Systemd:** Roda em background de forma contínua com auto-restart em caso de falhas.
* **Logs Profissionais:** Registra cada passo no `/var/log` com rotação automática configurada via `logrotate`.

## 📂 Estrutura do Sistema

Ao instalar o pacote `.deb`, o sistema distribui os arquivos nos seguintes diretórios padrão do Linux:

* `/opt/monitor-mailcow/monitor_mailcow.py` ➔ Core do daemon em Python.
* `/etc/mailcow-monitor/mailcow-monitor.conf` ➔ Arquivo de configuração seguro (não é sobrescrito em atualizações).
* `/etc/systemd/system/mailcow-monitor.service` ➔ Arquivo do serviço Systemd.
* `/etc/logrotate.d/monitor-mailcow` ➔ Regras de rotação de logs.
* `/var/log/monitor-mailcow.log` ➔ Arquivo principal de logs.

## 🚀 Instalação

Baixe a versão mais recente do pacote `.deb` na aba [Releases](#) deste repositório e instale via `dpkg`:

```bash
sudo dpkg -i monitor-mailcow.deb
```
*(As dependências `python3` e `git` serão exigidas e validadas automaticamente).*

## ⚙️ Configuração

O arquivo de configuração principal fica em `/etc/mailcow-monitor/mailcow-monitor.conf`.
Abra-o no seu editor de preferência e insira os dados do seu servidor de e-mail e Telegram:

```ini
[GERAL]
MAILCOW_DIR = /opt/mailcow-dockerized
# Intervalo (em horas) em que o daemon irá dormir entre cada checagem
INTERVALO_HORAS = 12

[SMTP]
SMTP_SERVER = smtp.seuprovedor.com
SMTP_PORT = 465
SMTP_USER = alertas@dominio.com.br
SMTP_PASS = sua-senha-segura
SENDER_NAME = Monitor Mailcow
SENDER_EMAIL = alertas@dominio.com.br
# Múltiplos e-mails devem ser separados por vírgula
RECIPIENT_EMAILS = admin@dominio.com.br, ti@dominio.com.br

[TELEGRAM]
# Deixe vazio caso não queira usar o Telegram
TELEGRAM_BOT_TOKEN = 1234567890:ABCdefGhIjkLmnopQRstUvwxYz
# Múltiplos IDs devem ser separados por vírgula
TELEGRAM_CHAT_ID = 11111111, 22222222
```

Após salvar as modificações, reinicie o daemon para aplicar as novas configurações:
```bash
sudo systemctl restart mailcow-monitor.service
```

## 🛠️ Comandos Úteis e Troubleshooting

Acompanhe o funcionamento do daemon em tempo real:
```bash
sudo tail -f /var/log/monitor-mailcow.log
```

Verifique o status do serviço no Systemd:
```bash
sudo systemctl status mailcow-monitor
```

Forçar um reenvio de alerta:
Se você quiser que o sistema envie os e-mails novamente na próxima checagem, basta apagar a memória da última versão avisada:
```bash
sudo rm /opt/monitor-mailcow/ultima_versao_avisada.txt
sudo systemctl restart mailcow-monitor
```

### ⚠️ Resolução de Problemas (Telegram 400 Bad Request)
Se os logs apontarem o erro `HTTP 400 (Bad Request: chat not found)`, significa que a API do Telegram bloqueou o envio por questões de anti-spam. 
**Solução:** O dono do Chat ID configurado deve abrir o aplicativo do Telegram, pesquisar o nome do Bot e enviar o comando `/start`. Apenas após a interação humana inicial o Bot tem permissão para disparar mensagens.

## 📦 Como compilar o pacote a partir do código-fonte (Build)

Para os desenvolvedores e Sysadmins que desejam modificar o código e gerar um novo pacote `.deb`, recrie a estrutura de diretórios do Debian e execute o comando de build garantindo a compatibilidade de compressão (`xz`) com distribuições mais antigas:

```bash
# Estrutura base necessária:
# monitor-mailcow-build/
# ├── DEBIAN/
# │   ├── control
# │   ├── conffiles
# │   ├── postinst  (chmod 755)
# │   └── prerm     (chmod 755)
# ├── etc/
# ├── opt/
# └── var/

# Comando de compilação:
dpkg-deb -Zxz --build monitor-mailcow-build monitor-mailcow.deb
```
**Desenvolvido e mantido para ambientes corporativos de alta criticidade.**
