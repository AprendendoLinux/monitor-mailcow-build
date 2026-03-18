#!/usr/bin/env python3
import subprocess
import urllib.request
import urllib.parse
import json
import smtplib
import ssl
import time
import os
import logging
import configparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

# ==========================================
#               CARREGAR CONFIG
# ==========================================
CONFIG_FILE = "/etc/mailcow-monitor/mailcow-monitor.conf"
SCRIPT_DIR = "/opt/monitor-mailcow"
ARQUIVO_CONTROLE = os.path.join(SCRIPT_DIR, "ultima_versao_avisada.txt")
ARQUIVO_LOG = "/var/log/monitor-mailcow.log"

config = configparser.ConfigParser()
if not config.read(CONFIG_FILE):
    print(f"ERRO FATAL: Arquivo de configuração {CONFIG_FILE} não encontrado.")
    exit(1)

MAILCOW_DIR = config.get("GERAL", "MAILCOW_DIR", fallback="/opt/mailcow-dockerized").strip().strip('"').strip("'")
INTERVALO_HORAS = config.getint("GERAL", "INTERVALO_HORAS", fallback=12)

SMTP_SERVER = config.get("SMTP", "SMTP_SERVER").strip().strip('"').strip("'")
SMTP_PORT = config.getint("SMTP", "SMTP_PORT")
SMTP_USER = config.get("SMTP", "SMTP_USER").strip().strip('"').strip("'")
SMTP_PASS = config.get("SMTP", "SMTP_PASS").strip().strip('"').strip("'")
SENDER_NAME = config.get("SMTP", "SENDER_NAME").strip().strip('"').strip("'")
SENDER_EMAIL = config.get("SMTP", "SENDER_EMAIL").strip().strip('"').strip("'")
RECIPIENT_EMAILS = config.get("SMTP", "RECIPIENT_EMAILS").strip().strip('"').strip("'")

TG_TOKEN = config.get("TELEGRAM", "TELEGRAM_BOT_TOKEN", fallback="").strip().strip('"').strip("'")
TG_CHAT_ID_RAW = config.get("TELEGRAM", "TELEGRAM_CHAT_ID", fallback="").strip().strip('"').strip("'")

if TG_TOKEN.lower().startswith("bot"):
    TG_TOKEN = TG_TOKEN[3:]

logging.basicConfig(
    filename=ARQUIVO_LOG, level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%d/%m/%Y %H:%M:%S'
)

def ler_ultima_versao_avisada():
    if os.path.exists(ARQUIVO_CONTROLE):
        with open(ARQUIVO_CONTROLE, "r") as f: return f.read().strip()
    return ""

def salvar_ultima_versao_avisada(versao):
    try:
        with open(ARQUIVO_CONTROLE, "w") as f: f.write(versao)
        logging.info(f"Controle atualizado. Versão {versao} notificada.")
    except Exception as e: logging.error(f"Erro ao salvar arquivo de controle: {e}")

def obter_versao_atual():
    try:
        res = subprocess.run(["git", "describe", "--tags"], cwd=MAILCOW_DIR, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except: return "Desconhecida"

def obter_dados_recente():
    url = "https://api.github.com/repos/mailcow/mailcow-dockerized/releases/latest"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Monitor-Mailcow/1.0'})
        with urllib.request.urlopen(req) as response:
            dados = json.loads(response.read().decode('utf-8'))
            return {"versao": dados.get("tag_name", "Desconhecida"), "notas": dados.get("body", "Sem notas.")}
    except Exception as e:
        logging.error(f"Erro API GitHub: {e}")
        return {"versao": "Desconhecida", "notas": ""}

def enviar_telegram(versao_atual, versao_nova):
    if not TG_TOKEN or not TG_CHAT_ID_RAW:
        logging.info("Telegram desabilitado (Token ou Chat ID ausentes).")
        return
        
    mensagem = (
        f"⚠️ *CRÍTICO: Atualização Mailcow*\n\n"
        f"Ação Imediata Requerida no Servidor.\n"
        f"🔻 Atual: `{versao_atual}`\n"
        f"🚀 Nova: `{versao_nova}`\n\n"
        f"Por favor, execute `./update.sh` no diretório do Mailcow."
    )
    
    # Prepara a lista de Chat IDs (caso o usuário tenha colocado vírgulas)
    chat_ids = [cid.strip() for cid in TG_CHAT_ID_RAW.split(",")]
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    
    for chat_id in chat_ids:
        if not chat_id: continue
        data = urllib.parse.urlencode({'chat_id': chat_id, 'text': mensagem, 'parse_mode': 'Markdown'}).encode('utf-8')
        try:
            logging.info(f"Enviando Telegram para o chat {chat_id}...")
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req) as response:
                logging.info(f"Alerta enviado ao Telegram ({chat_id}) com sucesso.")
        except urllib.error.HTTPError as e:
            erro_msg = e.read().decode('utf-8')
            logging.error(f"Falha HTTP ao enviar Telegram para {chat_id} ({e.code}): {erro_msg}")
        except Exception as e:
            logging.error(f"Falha ao enviar Telegram para {chat_id}: {e}")

def enviar_email(versao_atual, dados_nova):
    versao_nova = dados_nova["versao"]
    notas_lancamento = dados_nova["notas"]
    destinatarios = [email.strip() for email in RECIPIENT_EMAILS.split(",")]
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"CRÍTICO: Atualização Pendente no Servidor Mailcow ({versao_nova})"
    msg["From"] = formataddr((SENDER_NAME, SENDER_EMAIL))
    msg["To"] = ", ".join(destinatarios)

    html = f"""\
    <!DOCTYPE html>
    <html>
      <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; padding: 20px; color: #333; margin: 0;">
        <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 6px solid #d9534f; overflow: hidden;">
          <div style="background-color: #2b2b2b; padding: 20px; text-align: center;">
            <h1 style="color: #ff4d4d; margin: 0; font-size: 22px; text-transform: uppercase; letter-spacing: 1px;">⚠️ Alerta de Segurança e Estabilidade</h1>
          </div>
          <div style="padding: 30px;">
            <div style="font-size: 16px; font-weight: bold; color: #721c24; text-align: center; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px; background-color: #f8d7da; margin-bottom: 25px;">
              AÇÃO IMEDIATA REQUERIDA: ATUALIZAÇÃO DO MAILCOW PENDENTE
            </div>
            <p style="font-size: 15px; line-height: 1.6; margin-top: 0;">
              O sistema de monitoramento identificou que o servidor de e-mail está rodando uma versão defasada. <strong>A aplicação desta atualização não é opcional e vai muito além de uma simples manutenção de rotina.</strong>
            </p>
            <p style="font-size: 15px; line-height: 1.6;">
              Manter a infraestrutura de e-mail desatualizada expõe nossa rede a vulnerabilidades críticas de segurança, riscos severos de invasão, vazamento de dados e a alta probabilidade do domínio ser incluído em <em>blacklists</em> globais de spam.
            </p>
            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 25px 0; background: #f8f9fa; border-radius: 6px; border-left: 4px solid #2b2b2b;">
              <tr>
                <td width="50%" style="padding: 15px;">
                  <span style="display: block; font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px;">Versão Vulnerável (Atual)</span>
                  <span style="display: block; font-size: 20px; color: #d9534f; font-weight: bold;">{versao_atual}</span>
                </td>
                <td width="50%" style="padding: 15px; border-left: 1px solid #eaeaea;">
                  <span style="display: block; font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px;">Nova Versão (Segura)</span>
                  <span style="display: block; font-size: 20px; color: #5cb85c; font-weight: bold;">{versao_nova}</span>
                </td>
              </tr>
            </table>
            <div style="background-color: #fff3cd; border-left: 4px solid #ffecb5; padding: 20px; border-radius: 4px; margin-bottom: 25px;">
              <h4 style="margin: 0 0 10px 0; color: #856404; font-size: 16px; text-transform: uppercase;">Instrução Operacional</h4>
              <p style="margin: 0; font-size: 15px; color: #856404; font-weight: bold; line-height: 1.5;">
                Entre em contato IMEDIATAMENTE com o analista responsável pela infraestrutura do servidor para agendar a janela de atualização.
              </p>
            </div>
            <div>
              <h3 style="font-size: 14px; color: #2b2b2b; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 10px;">Relatório de Correções (Changelog):</h3>
              <div style="background-color: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; font-family: 'Courier New', Courier, monospace; font-size: 13px; max-height: 200px; overflow-y: auto; white-space: pre-wrap;">{notas_lancamento}</div>
            </div>
          </div>
          <div style="background-color: #f1f1f1; text-align: center; padding: 15px; font-size: 11px; color: #888; border-top: 1px solid #e5e5e5;">
            Notificação automatizada do Monitor de Infraestrutura e Segurança.
          </div>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        logging.info(f"Conectando ao SMTP ({SMTP_SERVER}:{SMTP_PORT})...")
        contexto = ssl.create_default_context()
        
        # Inteligência para detectar se é 465 (SSL) ou 587/25 (STARTTLS)
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=contexto)
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.ehlo()
            server.starttls(context=contexto)
            server.ehlo()
            
        with server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SENDER_EMAIL, destinatarios, msg.as_string())
            
        logging.info("E-mail enviado com sucesso.")
        return True 
    except Exception as e:
        logging.error(f"Falha SMTP: {e}")
        return False

def check_mailcow_updates():
    try:
        logging.info("Iniciando verificação do Mailcow...")
        res = subprocess.run(["./update.sh", "--check"], cwd=MAILCOW_DIR, capture_output=True, text=True)
        
        if "Updated code is available." in res.stdout:
            dados_nova = obter_dados_recente()
            versao_nova = dados_nova["versao"]
            ultima_avisada = ler_ultima_versao_avisada()
            
            if versao_nova != "Desconhecida" and versao_nova != ultima_avisada:
                logging.info(f"Nova versão pendente: {versao_nova}. Disparando alertas.")
                versao_atual = obter_versao_atual()
                
                enviar_telegram(versao_atual, versao_nova)
                
                if enviar_email(versao_atual, dados_nova):
                    salvar_ultima_versao_avisada(versao_nova)
            else:
                logging.info("Esta versão já foi notificada. Aguardando ação técnica.")
        else:
            logging.info("Sistema atualizado.")
            
    except Exception as e:
        logging.error(f"Erro fatal: {e}")

if __name__ == "__main__":
    logging.info(f"Daemon iniciado (PID {os.getpid()}). Intervalo configurado: {INTERVALO_HORAS}h.")
    while True:
        check_mailcow_updates()
        time.sleep(INTERVALO_HORAS * 3600)
