# Arquitetura

O projeto é um único processo Python (`monitor_mailcow.py`) executado como serviço systemd. Usa apenas a biblioteca padrão.

## Componentes

| Parte | Responsabilidade |
|---|---|
| `carregar_config()` | Lê o `.conf`, aplica padrões e encerra com código 78 em erro |
| `verificar_update()` | Executa `./update.sh --check` e classifica a saída |
| `obter_versao_atual()` | `git describe --tags` no `MAILCOW_DIR` |
| `obter_dados_recente()` | Última release e changelog via API do GitHub |
| `enviar_email()` / `enviar_telegram()` | Entrega por canal; retornam sucesso por canal |
| `ler_estado()` / `salvar_estado()` | Persistência em JSON com escrita atômica |
| `ciclo()` | Uma passada completa da lógica |
| `main()` | Loop com espera adaptativa |

## Classificação do `update.sh --check`

| Saída contém | Status | Significado |
|---|---|---|
| `Updated code is available.` | `pendente` | Há atualização |
| `No updates available` | `ok` | Está atualizado |
| qualquer outra coisa, timeout ou erro | `indeterminado` | Nada é enviado; o erro vai ao log |

## Máquina de estados

```
            status=pendente, versão nova
 (limpo) ──────────────────────────────────► PENDENTE ──┐
    ▲                                           │       │ canal falhou:
    │                                           │       │ reenvia só ele
    │ todos os canais entregaram               │       └───────────────┐
    │                                           ▼                       │
    └───────────────────────────────────── CONCLUÍDO ◄──────────────────┘
                                   (status=ok ou versão local = pendente,
                                    e versão local conhecida)
```

* **Limpo → Pendente:** `--check` diz que há atualização; consulta o GitHub; grava o estado e envia o alerta.
* **Pendente:** enquanto algum canal não entregou, tenta de novo a cada ciclo. Com todos entregues, apenas aguarda, sem novas chamadas ao GitHub.
* **Pendente → Concluído:** `status=ok` (ou versão local igual à pendente) **e** a versão local é conhecida. Grava `concluido` e envia o aviso.
* **Concluído → Limpo:** quando o aviso foi entregue em todos os canais, o estado `pendente` é apagado.
* **Nova release durante a pendência:** se o alerta anterior ainda não foi entregue, uma nova versão reinicia os canais, preservando `desde` (o início da exposição).
* **Telegram desabilitado** conta como entregue, para não travar o fluxo.

### Por que não comparar só versões?

Quem acompanha a branch `master` do Mailcow tem versões locais como `2026-11-26-gfcc4045ef` (commits após a tag), que nunca são iguais a uma tag como `2026-11b`. Por isso a conclusão é inferida principalmente por `No updates available`, e a comparação de versões é apenas um atalho.

## Formato do `estado.json`

```json
{
  "pendente": {
    "versao": "2026-11b",
    "versao_anterior": "2026-11-26-gfcc4045ef",
    "desde": "2026-11-19T15:28:22-03:00",
    "notas": "changelog da release",
    "alerta":   { "email": true, "telegram": true },
    "concluido": {
      "em": "2026-11-19T19:40:00-03:00",
      "versao_atual": "2026-11b",
      "aviso": { "email": false, "telegram": true }
    }
  }
}
```

* `pendente` é `null` (ou o arquivo `{}`) quando não há nada em andamento.
* `concluido` é `null` até a atualização ser detectada.
* `desde` é o início da exposição; o tempo de exposição no aviso é `concluido.em - desde`.
* O arquivo é gravado em `estado.json.tmp` e renomeado (`os.replace`), com modo 600.
* Se o JSON estiver corrompido, o daemon registra o erro e recomeça do zero.

## Migração do estado da 1.0.0

Se `estado.json` não existe e há `/opt/monitor-mailcow/ultima_versao_avisada.txt`:

* Versão local diferente da avisada: cria `pendente` com os canais marcados como já entregues, `desde` = data de modificação do arquivo antigo. Nada é reenviado e o aviso de conclusão sai quando a atualização for aplicada.
* Versão local igual à avisada: nada pendente.
* Versão local desconhecida: adia a migração.
* Depois, o arquivo antigo é renomeado para `.migrado`.

## Temporização

| Situação | Espera |
|---|---|
| Sem pendência | `INTERVALO_HORAS` |
| Com `pendente` no estado | `INTERVALO_PENDENTE_MINUTOS` |
| Exceção inesperada no ciclo | `INTERVALO_PENDENTE_MINUTOS` |

Timeouts: rede (GitHub, SMTP, Telegram) 30 s; `git describe` 30 s; `update.sh --check` 300 s.

## Decisões de projeto

* **Stdlib apenas:** sem `pip`, sem ambiente virtual, menos superfície de ataque.
* **Um arquivo de código:** simples de auditar.
* **Estado por canal:** falha parcial não causa spam nem perda de aviso.
* **Alerta único por versão:** evita fadiga de alertas; o aviso de conclusão fecha o ciclo.
* **Serviço como root:** o `update.sh` do Mailcow precisa ler o `mailcow.conf` e usar o Docker.
