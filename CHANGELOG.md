# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [1.1.2] - 2026-11-19

### Adicionado
- Arquivo `/usr/share/doc/monitor-mailcow/copyright` no pacote Debian (formato DEP-5, licença MIT).
- Licença MIT no repositório.

## [1.1.1] - 2026-11-19

### Corrigido
- Migração do estado antigo usa a data real do último alerta no cálculo do tempo de exposição.
- `estado.json` é gravado com modo 600.
- O changelog é buscado no GitHub quando o estado migrado não o possui.

## [1.1.0] - 2026-11-19

### Adicionado
- Aviso de conclusão por e-mail e Telegram depois da atualização do Mailcow, com versões, datas e tempo de exposição.
- Estado por canal em `/var/lib/monitor-mailcow/estado.json`, com migração automática do `ultima_versao_avisada.txt`.
- Ciclo curto (`INTERVALO_PENDENTE_MINUTOS`, padrão 15) enquanto há atualização pendente.
- Script `postrm` com limpeza no `purge`.
- Documentação completa em `docs/`.

### Alterado
- Telegram usa `parse_mode=HTML` com escape, em vez de Markdown.
- Falha de um canal não impede nem duplica o envio nos outros.
- Serviço com hardening (`NoNewPrivileges`, `PrivateTmp`, `ProtectHome`, `ProtectSystem=full`), `Restart=on-failure` e Python em modo isolado (`-I`).
- Log em modo 640 e arquivos do pacote com dono root.

### Corrigido
- Changelog do GitHub era inserido no HTML sem escape.
- Chamadas de rede e subprocessos sem timeout.
- Saída inesperada do `update.sh --check` ou falha da API do GitHub passavam silenciosamente.
- Erro de configuração causava loop de reinício (agora sai com código 78 e não reinicia).
- Token do Telegram podia aparecer nos logs de erro.

## [1.0.0]

- Versão inicial: alerta crítico por e-mail e Telegram quando há nova release do Mailcow.
