# Desenvolvimento

## Estrutura do repositório

```
.
├── README.md
├── CHANGELOG.md
├── docs/                          documentação
├── monitor-mailcow.deb            pacote compilado (também publicado nas Releases)
└── monitor-mailcow-build/         árvore do pacote Debian
    ├── DEBIAN/                    control, conffiles, postinst, prerm, postrm
    ├── etc/
    │   ├── mailcow-monitor/mailcow-monitor.conf
    │   ├── systemd/system/mailcow-monitor.service
    │   └── logrotate.d/monitor-mailcow
    └── opt/monitor-mailcow/monitor_mailcow.py
```

## Scripts do pacote

| Script | Quando roda | O que faz |
|---|---|---|
| `postinst` | Instalação e atualização | Cria `/var/lib/monitor-mailcow` (700), ajusta modos do `.conf` e do log, recarrega, habilita e reinicia o serviço |
| `prerm` | Antes de remover (`remove`) | Para e desabilita o serviço. Em atualizações (`upgrade`) não faz nada |
| `postrm` | Depois de remover | Recarrega o systemd. No `purge`, apaga estado, log e `/opt/monitor-mailcow` |

Todos protegem as chamadas ao `systemctl` com `[ -d /run/systemd/system ]` para funcionar em chroots e contêineres.

## Regra do conffile

`mailcow-monitor.conf` está em `DEBIAN/conffiles`. Se o arquivo mudar entre versões do pacote, o dpkg pergunta ao usuário que o editou. Portanto:

* **Não altere o `.conf` do pacote** sem necessidade real.
* Novas opções devem ser **opcionais no código**, com valor padrão, e documentadas em `docs/CONFIGURACAO.md`.

O serviço systemd e o logrotate **não** são conffiles e são sobrescritos a cada versão.

## Build do pacote

```bash
chmod 755 monitor-mailcow-build/DEBIAN/{postinst,prerm,postrm}
chmod 600 monitor-mailcow-build/etc/mailcow-monitor/mailcow-monitor.conf
find monitor-mailcow-build -name __pycache__ -prune -exec rm -rf {} +
dpkg-deb --root-owner-group -Zxz --build monitor-mailcow-build monitor-mailcow_<versão>_all.deb
```

* `--root-owner-group`: arquivos pertencem ao root no pacote, independentemente de quem compila.
* `-Zxz`: compatível com distribuições mais antigas.

Inspeção:

```bash
dpkg-deb -I monitor-mailcow_<versão>_all.deb     # metadados
dpkg-deb -c monitor-mailcow_<versão>_all.deb     # conteúdo e permissões
```

## Testando o código sem instalar

O código lê três variáveis de ambiente (veja [CONFIGURACAO.md](CONFIGURACAO.md#variáveis-de-ambiente-desenvolvimento-e-testes)). Com elas e um Mailcow falso é possível exercitar o ciclo inteiro:

```bash
T=$(mktemp -d)
mkdir -p $T/mc $T/state
( cd $T/mc && git init -q && git commit -q --allow-empty -m 1 && git tag 2026-09 )
printf '#!/bin/bash\ncat "$(dirname "$0")/.mode"\n' > $T/mc/update.sh && chmod +x $T/mc/update.sh
cat > $T/c.conf <<EOF
[GERAL]
MAILCOW_DIR = $T/mc
[SMTP]
SMTP_SERVER = x
SMTP_USER = u
SMTP_PASS = p
SENDER_NAME = M
SENDER_EMAIL = a@b
RECIPIENT_EMAILS = a@b
EOF

MAILCOW_MONITOR_CONF=$T/c.conf MAILCOW_MONITOR_STATE_DIR=$T/state MAILCOW_MONITOR_LOG=$T/log \
python3 -I - <<EOF
import sys
sys.path.insert(0, "monitor-mailcow-build/opt/monitor-mailcow")
import monitor_mailcow as m
m.enviar_email = lambda assunto, corpo: print("EMAIL:", assunto) or True
m.enviar_telegram = lambda texto: print("TELEGRAM:", texto.splitlines()[0]) or True
m.obter_dados_recente = lambda: {"versao": "2026-10", "notas": "changelog"}

open("$T/mc/.mode", "w").write("Updated code is available.\n")
m.ciclo()                                   # alerta
open("$T/mc/.mode", "w").write("No updates available.\n")
m.ciclo()                                   # conclusão
EOF
```

Cenários que vale cobrir ao mexer na lógica:

1. Alerta com falha em um canal e reenvio só dele.
2. Sem repetição do alerta já entregue.
3. Conclusão detectada, com falha e retry.
4. Migração do `ultima_versao_avisada.txt`.
5. Saída inesperada do `--check` (nada é enviado).
6. Versão local desconhecida (nada é enviado).

Teste dos templates (sem rede): `html_alerta(...)` e `html_concluido(...)` devem escapar conteúdo, por exemplo `<script>` no changelog.

## Convenções de código

* Python 3 com biblioteca padrão apenas.
* Código limpo, sem comentários excessivos; logs e mensagens em português.
* Nunca registrar o token do Telegram: passe mensagens de erro por `mascarar()`.
* Todo conteúdo externo que vai ao HTML passa por `_esc()`.
* Toda chamada de rede ou subprocesso tem `timeout`.
* Erro de configuração: sair com `EXIT_CONFIG` (78).

## Processo de release

1. Atualize `VERSAO_APP` em `monitor_mailcow.py` e `Version` em `DEBIAN/control`.
2. Atualize `CHANGELOG.md` e os selos de versão do `README.md`.
3. Compile o pacote e teste a **atualização por cima** da versão anterior numa máquina de teste.
4. Gere o checksum: `sha256sum monitor-mailcow_<versão>_all.deb > SHA256SUMS`.
5. Abra um PR, faça o merge e crie a tag `v<versão>`.
6. Publique a Release com o `.deb` e o `SHA256SUMS`:

```bash
gh release create v<versão> monitor-mailcow_<versão>_all.deb SHA256SUMS \
  --title "v<versão>" --notes-file notas.md
```

## Ideias futuras

* Reenvio periódico do alerta enquanto houver pendência (opcional).
* Testes automatizados e CI.
* Heartbeat/healthcheck do próprio daemon.
