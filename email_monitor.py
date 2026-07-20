import imaplib
import email
import time
import os
import pathlib
from email.header import decode_header

from whatsapp_web import send_whatsapp_web

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent


def load_dotenv(path):
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(SCRIPT_DIR / ".env")

IMAP_SERVER = os.environ["EMAIL_IMAP_SERVER"]
EMAIL = os.environ["EMAIL_USER"]
SENHA = os.environ["EMAIL_PASSWORD"]
NOTIFY_NUMBER = os.environ["NOTIFY_NUMBER"]


def send_whatsapp(texto):
    return send_whatsapp_web(NOTIFY_NUMBER, texto)


def conectar():
    m = imaplib.IMAP4_SSL(IMAP_SERVER, 993)
    m.login(EMAIL, SENHA)
    m.select("INBOX")
    return m


mail = conectar()
status, mensagens = mail.search(None, "ALL")
ids = mensagens[0].split()
ultimo_id = ids[-1] if ids else None

print("📧 Monitorando novos e-mails...")

while True:
    try:
        status, mensagens = mail.search(None, "ALL")
        ids = mensagens[0].split()

        if ids:
            ultimo = ids[-1]

            if ultimo != ultimo_id:
                ultimo_id = ultimo

                status, dados = mail.fetch(ultimo, "(RFC822)")

                for resposta in dados:
                    if isinstance(resposta, tuple):
                        msg = email.message_from_bytes(resposta[1])

                        assunto = decode_header(msg["Subject"])[0][0]
                        if isinstance(assunto, bytes):
                            assunto = assunto.decode(errors="ignore")

                        remetente = msg["From"]

                        corpo = ""

                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        corpo = payload.decode(errors="ignore")
                                        break
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                corpo = payload.decode(errors="ignore")

                        print("\n📩 Novo e-mail")
                        print("De:", remetente)
                        print("Assunto:", assunto)
                        print("Corpo:")
                        print(corpo[:300])

                        texto_wpp = (
                            f"📩 Novo e-mail\n"
                            f"De: {remetente}\n"
                            f"Assunto: {assunto}\n\n"
                            f"{corpo[:300]}"
                        )
                        if send_whatsapp(texto_wpp):
                            print("✅ Notificação enviada no WhatsApp.")
    except imaplib.IMAP4.abort:
        print("⚠️  Conexão IMAP caiu — reconectando...")
        mail = conectar()
    except Exception as exc:
        print(f"⚠️  Erro no ciclo: {type(exc).__name__}: {exc}")

    time.sleep(5)