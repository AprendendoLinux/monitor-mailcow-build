# 🛡️ Monitor Crítico de Atualizações - Mailcow

![versão](https://img.shields.io/badge/versão-1.1.2-blue)
![plataforma](https://img.shields.io/badge/Debian%20%2F%20Ubuntu-.deb-informational)
![python](https://img.shields.io/badge/Python-3%20(stdlib)-green)
![licença](https://img.shields.io/badge/licença-MIT-yellow)

Daemon para Debian/Ubuntu, escrito em Python (somente biblioteca padrão), que monitora o [Mailcow Dockerized](https://mailcow.email/) e avisa a equipe por **E-mail (HTML)** e **Telegram**:

1. quando existe uma **atualização pendente** (alerta crítico);
2. quando a atualização é **aplicada** (aviso de conclusão, com o tempo de exposição).

## ✨ Funcionalidades

* **Detecção** via `./update.sh --check` + API de releases do GitHub (versão e changelog).
* **Alerta crítico** por e-mail HTML e Telegram, com versão atual, nova versão e changelog.
* **Aviso de conclusão** automático depois que você roda o `update.sh`, no mesmo padrão visual, em verde.
* **Estado por canal:** se um canal falhar, só ele é reenviado no ciclo seguinte.
* **Sem repetição:** um alerta e um aviso de conclusão por versão.
* **Ciclo adaptativo:** `INTERVALO_HORAS` (padrão 12h) normalmente; `INTERVALO_PENDENTE_MINUTOS` (padrão 15 min) enquanto há atualização pendente.
* **Seguro por padrão:** changelog escapado no HTML, timeouts em toda chamada externa, token mascarado nos logs, serviço com hardening do systemd.
* **Pacote `.deb`** com systemd, logrotate e atualização por cima sem perder configuração ou estado.

## ⚡ Início rápido

```bash
# 1. Baixe o .deb e o SHA256SUMS na aba Releases e confira a integridade
sha256sum -c SHA256SUMS

# 2. Instale
sudo dpkg -i monitor-mailcow_1.1.2_all.deb

# 3. Configure SMTP, destinatários e Telegram
sudo nano /etc/mailcow-monitor/mailcow-monitor.conf
sudo systemctl restart mailcow-monitor

# 4. Acompanhe
sudo tail -f /var/log/monitor-mailcow.log
```

Requisitos: Debian/Ubuntu com `systemd`, `python3` e `git`; Mailcow Dockerized instalado como clone git; acesso root.

Já usa a 1.0.0? Instale o novo pacote por cima: veja [Atualização](docs/OPERACAO.md#atualização-do-pacote).

## 🔄 Como funciona

```
update.sh --check ──► "Updated code is available."
        │
        ▼
 consulta GitHub ─► envia ALERTA (e-mail + Telegram) ─► estado: pendente
        │
        ▼  (você roda ./update.sh no Mailcow)
 update.sh --check ──► "No updates available." + versão local conhecida
        │
        ▼
 envia AVISO DE CONCLUSÃO (e-mail + Telegram) ─► estado: limpo
```

O daemon **não repete** o alerta enquanto a atualização não é aplicada; só reenvia se algum canal tiver falhado. Detalhes em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## 📚 Documentação

| Documento | Conteúdo |
|---|---|
| [docs/CONFIGURACAO.md](docs/CONFIGURACAO.md) | Todas as opções do `.conf`, SMTP, Telegram (como obter token e chat ID) |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Fluxo do ciclo, máquina de estados, formato do `estado.json`, decisões de projeto |
| [docs/OPERACAO.md](docs/OPERACAO.md) | Instalação, atualização, operação diária, testes, desinstalação |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Mensagens de log, causas e soluções |
| [docs/SEGURANCA.md](docs/SEGURANCA.md) | Modelo de ameaças, permissões, hardening, boas práticas |
| [docs/DESENVOLVIMENTO.md](docs/DESENVOLVIMENTO.md) | Estrutura do código, build do `.deb`, testes, processo de release |
| [CHANGELOG.md](CHANGELOG.md) | Histórico de versões |

## 📂 Arquivos no sistema

| Caminho | Função |
|---|---|
| `/opt/monitor-mailcow/monitor_mailcow.py` | Código do daemon |
| `/etc/mailcow-monitor/mailcow-monitor.conf` | Configuração (modo 600; preservada em atualizações) |
| `/var/lib/monitor-mailcow/estado.json` | Estado persistente |
| `/etc/systemd/system/mailcow-monitor.service` | Serviço systemd |
| `/etc/logrotate.d/monitor-mailcow` | Rotação de logs (diária, 7 arquivos) |
| `/var/log/monitor-mailcow.log` | Log (modo 640) |

## ⚠️ Limitações conhecidas

* Depende das frases `Updated code is available.` e `No updates available.` do `update.sh` do Mailcow. Se mudarem, o daemon registra `Saída inesperada` no log e não envia nada.
* Não reenvia o alerta periodicamente enquanto a atualização estiver pendente.
* O serviço roda como root (necessário para o `update.sh`); veja [docs/SEGURANCA.md](docs/SEGURANCA.md).
* Sem testes automatizados no repositório.

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE).

---
**Desenvolvido e mantido para ambientes corporativos de alta criticidade.** · v1.1.2
