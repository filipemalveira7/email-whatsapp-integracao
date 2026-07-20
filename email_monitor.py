import imaplib
import email
import time
import json
import os
import pathlib
import urllib.error
import urllib.request
from email.header import decode_header

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
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "").strip()
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
WHATSAPP_API_VERSION = os.environ.get("WHATSAPP_API_VERSION", "v20.0").strip()
NOTIFY_NUMBER = os.environ["NOTIFY_NUMBER"]


def send_whatsapp(texto):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print("⚠️  WHATSAPP_TOKEN/WHATSAPP_PHONE_NUMBER_ID vazio no .env — pulei o envio pro WhatsApp.")
        return False
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": NOTIFY_NUMBER,
        "type": "text",
        "text": {"body": texto},
    }).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
        return True
    except urllib.error.HTTPError as exc:
        print(f"❌ WhatsApp Cloud API HTTP {exc.code}: {exc.read().decode(errors='ignore')[:300]}")
    except Exception as exc:
        print(f"❌ WhatsApp Cloud API erro: {exc}")
    return False


mail = imaplib.IMAP4_SSL(IMAP_SERVER, 993)
mail.login(EMAIL, SENHA)
mail.select("INBOX")

status, mensagens = mail.search(None, "ALL")
ids = mensagens[0].split()
ultimo_id = ids[-1] if ids else None

print("📧 Monitorando novos e-mails...")

while True:
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

    time.sleep(5)