import imaplib
import email
import os
import pathlib
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

   #conecta ao outlook
mail = imaplib.IMAP4_SSL(IMAP_SERVER, 993)
mail.login(EMAIL, SENHA)
print("✅ Conectado com sucesso!")
    
    #abre caixa de entrada
mail.select("INBOX")

    #busca os emails recentes
status, mensagens = mail.search(None, "ALL")

ids = mensagens[0].split()

for msg_id in ids[-5:]:
    status, dados = mail.fetch(msg_id, "(RFC822)")

    for resposta in dados:
        if isinstance(resposta, tuple):
            msg = email.message_from_bytes(resposta[1])

            assunto = decode_header(msg["Subject"])[0][0]
            if isinstance(assunto, bytes):
                assunto = assunto.decode(errors="ignore")

            remetente = msg["From"]
            data = msg["Date"]

            print("=" * 50)
            print("De:", remetente)
            print("Assunto:", assunto)
            print("Data:", data)
mail.logout()