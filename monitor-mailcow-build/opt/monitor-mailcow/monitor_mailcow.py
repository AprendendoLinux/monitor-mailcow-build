#!/usr/bin/env python3
import configparser
import html
import json
import logging
import os
import smtplib
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

VERSAO_APP = "1.1.2"
EXIT_CONFIG = 78
TIMEOUT_REDE = 30
TIMEOUT_CHECK = 300

CONFIG_FILE = os.environ.get("MAILCOW_MONITOR_CONF", "/etc/mailcow-monitor/mailcow-monitor.conf")
STATE_DIR = os.environ.get("MAILCOW_MONITOR_STATE_DIR", "/var/lib/monitor-mailcow")
ARQUIVO_ESTADO = os.path.join(STATE_DIR, "estado.json")
ARQUIVO_LEGADO = "/opt/monitor-mailcow/ultima_versao_avisada.txt"
ARQUIVO_LOG = os.environ.get("MAILCOW_MONITOR_LOG", "/var/log/monitor-mailcow.log")

DESCONHECIDA = "Desconhecida"


def _limpa(valor):
    return valor.strip().strip('"').strip("'")


def carregar_config():
    cfg = configparser.ConfigParser()
    if not cfg.read(CONFIG_FILE):
        print(f"ERRO FATAL: configuração {CONFIG_FILE} não encontrada.", file=sys.stderr)
        sys.exit(EXIT_CONFIG)

    def get(secao, chave, fallback=None):
        try:
            return _limpa(cfg.get(secao, chave))
        except (configparser.NoSectionError, configparser.NoOptionError):
            if fallback is None:
                print(f"ERRO FATAL: [{secao}] {chave} ausente em {CONFIG_FILE}.", file=sys.stderr)
                sys.exit(EXIT_CONFIG)
            return fallback

    def get_int(secao, chave, fallback):
        try:
            return int(get(secao, chave, str(fallback)))
        except ValueError:
            print(f"ERRO FATAL: [{secao}] {chave} deve ser um número inteiro.", file=sys.stderr)
            sys.exit(EXIT_CONFIG)

    c = {
        "mailcow_dir": get("GERAL", "MAILCOW_DIR", "/opt/mailcow-dockerized"),
        "intervalo_horas": get_int("GERAL", "INTERVALO_HORAS", 12),
        "intervalo_pendente_min": get_int("GERAL", "INTERVALO_PENDENTE_MINUTOS", 15),
        "smtp_server": get("SMTP", "SMTP_SERVER"),
        "smtp_port": get_int("SMTP", "SMTP_PORT", 465),
        "smtp_user": get("SMTP", "SMTP_USER"),
        "smtp_pass": get("SMTP", "SMTP_PASS"),
        "sender_name": get("SMTP", "SENDER_NAME"),
        "sender_email": get("SMTP", "SENDER_EMAIL"),
        "recipients": get("SMTP", "RECIPIENT_EMAILS"),
        "tg_token": get("TELEGRAM", "TELEGRAM_BOT_TOKEN", ""),
        "tg_chats": get("TELEGRAM", "TELEGRAM_CHAT_ID", ""),
    }
    if c["tg_token"].lower().startswith("bot"):
        c["tg_token"] = c["tg_token"][3:]
    c["intervalo_horas"] = max(c["intervalo_horas"], 1)
    c["intervalo_pendente_min"] = max(c["intervalo_pendente_min"], 1)
    return c


CFG = carregar_config()

logging.basicConfig(
    filename=ARQUIVO_LOG, level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s", datefmt="%d/%m/%Y %H:%M:%S",
)


def mascarar(texto):
    token = CFG["tg_token"]
    return str(texto).replace(token, "***") if token else str(texto)


def agora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fmt_data(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return "-"


def fmt_duracao(inicio, fim):
    try:
        seg = int((datetime.fromisoformat(fim) - datetime.fromisoformat(inicio)).total_seconds())
    except (TypeError, ValueError):
        return "-"
    seg = max(seg, 0)
    d, resto = divmod(seg, 86400)
    h, resto = divmod(resto, 3600)
    m = resto // 60
    if d:
        return f"{d}d {h}h {m}min"
    if h:
        return f"{h}h {m}min"
    return f"{m}min"


# ==========================================
#                 ESTADO
# ==========================================
def ler_estado():
    if os.path.exists(ARQUIVO_ESTADO):
        try:
            with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            logging.error(f"Estado ilegível ({e}); recomeçando do zero.")
            return {}
    return migrar_estado_legado()


def salvar_estado(estado):
    try:
        os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
        tmp = ARQUIVO_ESTADO + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, ARQUIVO_ESTADO)
    except OSError as e:
        logging.error(f"Erro ao salvar estado: {e}")


def migrar_estado_legado():
    if not os.path.exists(ARQUIVO_LEGADO):
        return {}
    try:
        with open(ARQUIVO_LEGADO, "r") as f:
            antiga = f.read().strip()
    except OSError as e:
        logging.error(f"Erro ao ler arquivo legado: {e}")
        return {}
    local = obter_versao_atual()
    if local == DESCONHECIDA:
        return {}
    estado = {}
    if antiga and antiga != local:
        try:
            desde = datetime.fromtimestamp(os.path.getmtime(ARQUIVO_LEGADO)).astimezone().isoformat(timespec="seconds")
        except OSError:
            desde = agora()
        estado["pendente"] = {
            "versao": antiga, "versao_anterior": local, "desde": desde,
            "alerta": {"email": True, "telegram": True}, "concluido": None,
        }
    salvar_estado(estado)
    try:
        os.rename(ARQUIVO_LEGADO, ARQUIVO_LEGADO + ".migrado")
    except OSError:
        pass
    logging.info(f"Estado legado migrado (versão avisada: {antiga or '-'}, local: {local}).")
    return estado


# ==========================================
#              FONTES DE VERSÃO
# ==========================================
def obter_versao_atual():
    try:
        res = subprocess.run(["git", "describe", "--tags"], cwd=CFG["mailcow_dir"],
                             capture_output=True, text=True, check=True, timeout=30)
        return res.stdout.strip() or DESCONHECIDA
    except (OSError, subprocess.SubprocessError) as e:
        logging.warning(f"Não foi possível obter a versão local: {e}")
        return DESCONHECIDA


def verificar_update():
    """Retorna 'pendente', 'ok' ou 'indeterminado'."""
    try:
        res = subprocess.run(["./update.sh", "--check"], cwd=CFG["mailcow_dir"],
                             capture_output=True, text=True, timeout=TIMEOUT_CHECK)
    except (OSError, subprocess.SubprocessError) as e:
        logging.error(f"Falha ao executar update.sh --check: {e}")
        return "indeterminado"
    if "Updated code is available." in res.stdout:
        return "pendente"
    if "No updates available" in res.stdout:
        return "ok"
    logging.error(f"Saída inesperada do update.sh --check (rc={res.returncode}): "
                  f"{(res.stdout + res.stderr).strip()[:300]}")
    return "indeterminado"


def obter_dados_recente():
    url = "https://api.github.com/repos/mailcow/mailcow-dockerized/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"Monitor-Mailcow/{VERSAO_APP}"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_REDE) as r:
            dados = json.loads(r.read().decode("utf-8"))
        return {"versao": dados.get("tag_name") or DESCONHECIDA, "notas": dados.get("body") or "Sem notas."}
    except Exception as e:
        logging.error(f"Erro API GitHub: {e}")
        return {"versao": DESCONHECIDA, "notas": ""}


# ==========================================
#                  CANAIS
# ==========================================
def enviar_telegram(mensagem_html):
    """True se entregue a ao menos um chat, ou se o Telegram está desabilitado."""
    token, chats_raw = CFG["tg_token"], CFG["tg_chats"]
    if not token or not chats_raw:
        logging.info("Telegram desabilitado (token ou chat ID ausentes).")
        return True

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chats = [c.strip() for c in chats_raw.split(",") if c.strip()]
    ok = 0
    for chat_id in chats:
        data = urllib.parse.urlencode({
            "chat_id": chat_id, "text": mensagem_html,
            "parse_mode": "HTML", "disable_web_page_preview": "true",
        }).encode("utf-8")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=TIMEOUT_REDE):
                pass
            logging.info(f"Telegram entregue ao chat {chat_id}.")
            ok += 1
        except urllib.error.HTTPError as e:
            corpo = e.read().decode("utf-8", "replace")
            logging.error(f"Telegram {chat_id} falhou (HTTP {e.code}): {mascarar(corpo)}")
        except Exception as e:
            logging.error(f"Telegram {chat_id} falhou: {mascarar(e)}")
    return ok > 0


def enviar_email(assunto, corpo_html):
    """True se entregue a ao menos um destinatário."""
    destinatarios = [e.strip() for e in CFG["recipients"].split(",") if e.strip()]
    if not destinatarios:
        logging.error("Nenhum destinatário de e-mail configurado.")
        return False
    try:
        logging.info(f"Conectando ao SMTP ({CFG['smtp_server']}:{CFG['smtp_port']})...")
        ctx = ssl.create_default_context()
        if CFG["smtp_port"] == 465:
            server = smtplib.SMTP_SSL(CFG["smtp_server"], CFG["smtp_port"], context=ctx, timeout=TIMEOUT_REDE)
        else:
            server = smtplib.SMTP(CFG["smtp_server"], CFG["smtp_port"], timeout=TIMEOUT_REDE)
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
        ok = 0
        with server:
            server.login(CFG["smtp_user"], CFG["smtp_pass"])
            for dest in destinatarios:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = assunto
                msg["From"] = formataddr((CFG["sender_name"], CFG["sender_email"]))
                msg["To"] = dest
                msg.attach(MIMEText(corpo_html, "html", "utf-8"))
                try:
                    server.sendmail(CFG["sender_email"], dest, msg.as_string())
                    logging.info(f"E-mail entregue para: {dest}")
                    ok += 1
                except Exception as e:
                    logging.error(f"Erro ao enviar para {dest}: {e}")
        return ok > 0
    except Exception as e:
        logging.error(f"Falha de conexão SMTP: {e}")
        return False


# ==========================================
#                 TEMPLATES
# ==========================================
def _esc(v):
    return html.escape(str(v))


def _moldura(cor, cor_titulo, titulo, faixa, fundo_faixa, borda_faixa, cor_faixa, miolo):
    return f"""\
<!DOCTYPE html>
<html>
  <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; padding: 20px; color: #333; margin: 0;">
    <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 6px solid {cor}; overflow: hidden;">
      <div style="background-color: #2b2b2b; padding: 20px; text-align: center;">
        <h1 style="color: {cor_titulo}; margin: 0; font-size: 22px; text-transform: uppercase; letter-spacing: 1px;">{titulo}</h1>
      </div>
      <div style="padding: 30px;">
        <div style="font-size: 16px; font-weight: bold; color: {cor_faixa}; text-align: center; border: 1px solid {borda_faixa}; padding: 15px; border-radius: 5px; background-color: {fundo_faixa}; margin-bottom: 25px;">
          {faixa}
        </div>
{miolo}
      </div>
      <div style="background-color: #f1f1f1; text-align: center; padding: 15px; font-size: 11px; color: #888; border-top: 1px solid #e5e5e5;">
        Notificação automatizada do Monitor de Infraestrutura e Segurança &middot; v{VERSAO_APP}
      </div>
    </div>
  </body>
</html>
"""


def _bloco_versoes(rotulo_a, valor_a, cor_a, rotulo_b, valor_b, cor_b):
    return f"""\
        <table width="100%" cellpadding="0" cellspacing="0" style="margin: 25px 0; background: #f8f9fa; border-radius: 6px; border-left: 4px solid #2b2b2b;">
          <tr>
            <td width="50%" style="padding: 15px;">
              <span style="display: block; font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px;">{rotulo_a}</span>
              <span style="display: block; font-size: 20px; color: {cor_a}; font-weight: bold;">{_esc(valor_a)}</span>
            </td>
            <td width="50%" style="padding: 15px; border-left: 1px solid #eaeaea;">
              <span style="display: block; font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px;">{rotulo_b}</span>
              <span style="display: block; font-size: 20px; color: {cor_b}; font-weight: bold;">{_esc(valor_b)}</span>
            </td>
          </tr>
        </table>"""


def _bloco_changelog(notas):
    return f"""\
        <div>
          <h3 style="font-size: 14px; color: #2b2b2b; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 10px;">Relatório de Correções (Changelog):</h3>
          <div style="background-color: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; font-family: 'Courier New', Courier, monospace; font-size: 13px; max-height: 200px; overflow-y: auto; white-space: pre-wrap;">{_esc(notas)}</div>
        </div>"""


def html_alerta(versao_atual, versao_nova, notas):
    miolo = f"""\
        <p style="font-size: 15px; line-height: 1.6; margin-top: 0;">
          O sistema de monitoramento identificou que o servidor de e-mail está rodando uma versão defasada. <strong>A aplicação desta atualização não é opcional e vai muito além de uma simples manutenção de rotina.</strong>
        </p>
        <p style="font-size: 15px; line-height: 1.6;">
          Manter a infraestrutura de e-mail desatualizada expõe nossa rede a vulnerabilidades críticas de segurança, riscos severos de invasão, vazamento de dados e a alta probabilidade do domínio ser incluído em <em>blacklists</em> globais de spam.
        </p>
{_bloco_versoes("Versão Vulnerável (Atual)", versao_atual, "#d9534f", "Nova Versão (Segura)", versao_nova, "#5cb85c")}
        <div style="background-color: #fff3cd; border-left: 4px solid #ffecb5; padding: 20px; border-radius: 4px; margin-bottom: 25px;">
          <h4 style="margin: 0 0 10px 0; color: #856404; font-size: 16px; text-transform: uppercase;">Instrução Operacional</h4>
          <p style="margin: 0; font-size: 15px; color: #856404; font-weight: bold; line-height: 1.5;">
            Entre em contato IMEDIATAMENTE com o analista responsável pela infraestrutura do servidor para agendar a janela de atualização.
          </p>
        </div>
{_bloco_changelog(notas)}"""
    return _moldura("#d9534f", "#ff4d4d", "⚠️ Alerta de Segurança e Estabilidade",
                    "AÇÃO IMEDIATA REQUERIDA: ATUALIZAÇÃO DO MAILCOW PENDENTE",
                    "#f8d7da", "#f5c6cb", "#721c24", miolo)


def html_concluido(versao_anterior, versao_nova, desde, concluido_em, notas):
    miolo = f"""\
        <p style="font-size: 15px; line-height: 1.6; margin-top: 0;">
          O sistema de monitoramento confirmou que o servidor de e-mail <strong>foi atualizado com sucesso</strong> e agora roda a versão mais recente. A exposição às vulnerabilidades da versão anterior foi encerrada.
        </p>
{_bloco_versoes("Versão Anterior", versao_anterior, "#888888", "Versão Atual (Segura)", versao_nova, "#5cb85c")}
        <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 25px 0; background: #f8f9fa; border-radius: 6px; border-left: 4px solid #5cb85c;">
          <tr>
            <td style="padding: 15px; font-size: 14px; line-height: 1.8; color: #333;">
              <strong>Alerta emitido em:</strong> {fmt_data(desde)}<br>
              <strong>Atualização confirmada em:</strong> {fmt_data(concluido_em)}<br>
              <strong>Tempo de exposição:</strong> {fmt_duracao(desde, concluido_em)}
            </td>
          </tr>
        </table>
        <div style="background-color: #d4edda; border-left: 4px solid #c3e6cb; padding: 20px; border-radius: 4px; margin-bottom: 25px;">
          <h4 style="margin: 0 0 10px 0; color: #155724; font-size: 16px; text-transform: uppercase;">Nenhuma ação adicional necessária</h4>
          <p style="margin: 0; font-size: 15px; color: #155724; line-height: 1.5;">
            Recomenda-se apenas validar o envio e o recebimento de e-mails e o acesso ao painel de administração.
          </p>
        </div>
{_bloco_changelog(notas)}"""
    return _moldura("#5cb85c", "#5cff9d", "✅ Atualização Concluída",
                    "AÇÃO CONCLUÍDA: MAILCOW ATUALIZADO COM SUCESSO",
                    "#d4edda", "#c3e6cb", "#155724", miolo)


def tg_alerta(versao_atual, versao_nova):
    return (
        "⚠️ <b>CRÍTICO: Atualização Mailcow</b>\n\n"
        "Ação imediata requerida no servidor.\n"
        f"🔻 Atual: <code>{_esc(versao_atual)}</code>\n"
        f"🚀 Nova: <code>{_esc(versao_nova)}</code>\n\n"
        "Execute <code>./update.sh</code> no diretório do Mailcow."
    )


def tg_concluido(versao_anterior, versao_nova, desde, concluido_em):
    return (
        "✅ <b>Mailcow atualizado</b>\n\n"
        f"🔹 Anterior: <code>{_esc(versao_anterior)}</code>\n"
        f"🟢 Atual: <code>{_esc(versao_nova)}</code>\n"
        f"⏱️ Tempo de exposição: {fmt_duracao(desde, concluido_em)}\n"
        f"🕒 Confirmado em: {fmt_data(concluido_em)}"
    )


# ==========================================
#                  CICLO
# ==========================================
def despachar(canais, assunto, corpo_html, corpo_tg):
    """Envia apenas aos canais ainda não entregues e atualiza o dicionário `canais`."""
    if not canais.get("telegram"):
        canais["telegram"] = enviar_telegram(corpo_tg)
    if not canais.get("email"):
        canais["email"] = enviar_email(assunto, corpo_html)
    return all(canais.get(c) for c in ("email", "telegram"))


def ciclo():
    logging.info("Iniciando verificação do Mailcow...")
    estado = ler_estado()
    pend = estado.get("pendente")
    status = verificar_update()
    local = obter_versao_atual()

    if status == "pendente":
        precisa_github = not pend or pend.get("concluido") or not all(pend["alerta"].get(c) for c in ("email", "telegram"))
        dados = obter_dados_recente() if precisa_github else None

        if dados is not None:
            nova = dados["versao"]
            if nova == DESCONHECIDA:
                logging.warning("Versão nova indisponível via GitHub; tentando no próximo ciclo.")
                return estado
            if not pend or pend.get("concluido") or pend["versao"] != nova:
                pend = {
                    "versao": nova, "versao_anterior": local,
                    "desde": pend["desde"] if pend and not pend.get("concluido") else agora(),
                    "alerta": {"email": False, "telegram": False}, "concluido": None,
                }
                logging.info(f"Nova versão pendente: {nova}.")
            pend["notas"] = dados["notas"]
            estado["pendente"] = pend
            salvar_estado(estado)
            completo = despachar(
                pend["alerta"],
                f"CRÍTICO: Atualização Pendente no Servidor Mailcow ({nova})",
                html_alerta(pend["versao_anterior"], nova, dados["notas"]),
                tg_alerta(pend["versao_anterior"], nova),
            )
            salvar_estado(estado)
            if completo:
                logging.info("Alerta entregue em todos os canais.")
        else:
            logging.info("Versão já notificada. Aguardando atualização.")
        return estado

    if pend and not pend.get("concluido") and local != DESCONHECIDA and status in ("ok", "indeterminado"):
        if local == pend["versao"] or status == "ok":
            pend["concluido"] = {
                "em": agora(), "versao_atual": local,
                "aviso": {"email": False, "telegram": False},
            }
            logging.info(f"Atualização confirmada: {pend['versao_anterior']} -> {local}.")
            salvar_estado(estado)

    if pend and pend.get("concluido"):
        c = pend["concluido"]
        if "notas" not in pend:
            pend["notas"] = obter_dados_recente()["notas"] or "Sem notas."
        completo = despachar(
            c["aviso"],
            f"CONCLUÍDO: Servidor Mailcow Atualizado ({c['versao_atual']})",
            html_concluido(pend["versao_anterior"], c["versao_atual"], pend["desde"], c["em"], pend.get("notas", "")),
            tg_concluido(pend["versao_anterior"], c["versao_atual"], pend["desde"], c["em"]),
        )
        if completo:
            logging.info("Aviso de conclusão entregue em todos os canais.")
            estado["pendente"] = None
        salvar_estado(estado)
    elif status == "ok":
        logging.info("Sistema atualizado.")
    return estado


def proxima_espera(estado):
    if estado.get("pendente"):
        return CFG["intervalo_pendente_min"] * 60
    return CFG["intervalo_horas"] * 3600


def main():
    logging.info(f"Daemon v{VERSAO_APP} iniciado (PID {os.getpid()}). "
                 f"Intervalo: {CFG['intervalo_horas']}h (pendente: {CFG['intervalo_pendente_min']}min).")
    while True:
        try:
            estado = ciclo()
        except Exception:
            logging.exception("Erro inesperado no ciclo")
            estado = {"pendente": True}
        time.sleep(proxima_espera(estado))


if __name__ == "__main__":
    main()
