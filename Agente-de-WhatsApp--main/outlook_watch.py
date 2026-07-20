#!/usr/bin/env python3
"""
outlook_watch.py — monitora o Outlook (Microsoft Graph) e notifica e-mail novo via WhatsApp (Zappfy)

Modos:
  login   roda o fluxo device-code uma vez (login interativo), salva token em outlook_token.json
  pull    checa a caixa de entrada uma vez, notifica e-mails novos desde o último check
  watch   loop infinito: pull a cada N segundos (--interval, default 60)

Auth: OAuth2 device-code flow (Microsoft Graph, permissão delegada Mail.Read).
Token cache local em outlook_token.json (no .gitignore) — refresh automático depois do
primeiro login, sem repetir o fluxo interativo a cada execução.

Vars .env:
  MS_CLIENT_ID          obrigatório — client_id do app registrado no Azure AD
  MS_TENANT_ID          obrigatório — tenant_id (ou "common" pra multi-tenant)
  OUTLOOK_NOTIFY_NUMBER opcional — default: OPERATOR_NUMBER, depois TEST_NUMBER
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from disparo import SCRIPT_DIR, load_dotenv, normalize_phone_e164_br, send_with_retry

load_dotenv(SCRIPT_DIR / ".env")

MS_CLIENT_ID = os.environ.get("MS_CLIENT_ID", "").strip()
MS_TENANT_ID = os.environ.get("MS_TENANT_ID", "").strip()
NOTIFY_NUMBER_RAW = (
    os.environ.get("OUTLOOK_NOTIFY_NUMBER", "").strip()
    or os.environ.get("OPERATOR_NUMBER", "").strip()
    or os.environ.get("TEST_NUMBER", "").strip()
)
NOTIFY_NUMBER = normalize_phone_e164_br(NOTIFY_NUMBER_RAW)

TOKEN_CACHE = SCRIPT_DIR / "outlook_token.json"
STATE_FILE = SCRIPT_DIR / "outlook_state.json"
LOGS_DIR = SCRIPT_DIR / "logs"

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPE = "offline_access Mail.Read"


def require_ms_config():
    if not MS_CLIENT_ID or not MS_TENANT_ID:
        print(
            "ERRO: MS_CLIENT_ID / MS_TENANT_ID ausentes no .env.\n"
            "Registre um app no Azure AD (App registrations) e preencha o .env antes de rodar 'login'.",
            file=sys.stderr,
        )
        sys.exit(2)


def _post_form(url, params, timeout=30):
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8"))


def save_token(tok):
    tok["_saved_at"] = int(time.time())
    TOKEN_CACHE.write_text(json.dumps(tok), encoding="utf-8")


def load_token():
    if not TOKEN_CACHE.exists():
        return None
    return json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))


def device_code_login():
    require_ms_config()
    url = f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/devicecode"
    resp = _post_form(url, {"client_id": MS_CLIENT_ID, "scope": SCOPE})
    if "device_code" not in resp:
        print(f"ERRO ao iniciar device code: {resp}", file=sys.stderr)
        sys.exit(1)

    print(resp["message"])

    token_url = f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/token"
    interval = resp.get("interval", 5)
    deadline = time.time() + resp.get("expires_in", 900)
    while time.time() < deadline:
        time.sleep(interval)
        tok = _post_form(
            token_url,
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": MS_CLIENT_ID,
                "device_code": resp["device_code"],
            },
        )
        if "access_token" in tok:
            save_token(tok)
            print("✅ login OK — token salvo em outlook_token.json")
            return tok
        err = tok.get("error")
        if err == "authorization_pending":
            continue
        print(f"ERRO: {tok}", file=sys.stderr)
        sys.exit(1)

    print("ERRO: tempo esgotado esperando login.", file=sys.stderr)
    sys.exit(1)


def refresh_access_token(tok):
    url = f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/token"
    new_tok = _post_form(
        url,
        {
            "grant_type": "refresh_token",
            "client_id": MS_CLIENT_ID,
            "refresh_token": tok["refresh_token"],
            "scope": SCOPE,
        },
    )
    if "access_token" not in new_tok:
        print(f"ERRO ao renovar token: {new_tok}. Rode: python3 outlook_watch.py login", file=sys.stderr)
        sys.exit(1)
    save_token(new_tok)
    return new_tok


def get_access_token():
    require_ms_config()
    tok = load_token()
    if not tok:
        print("Nenhum token salvo. Rode primeiro: python3 outlook_watch.py login", file=sys.stderr)
        sys.exit(2)
    age = int(time.time()) - tok.get("_saved_at", 0)
    if age >= tok.get("expires_in", 3600) - 60:
        tok = refresh_access_token(tok)
    return tok["access_token"]


def graph_get(path, access_token, timeout=30):
    req = urllib.request.Request(
        f"{GRAPH_BASE}{path}", headers={"Authorization": f"Bearer {access_token}"}, method="GET"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"last_checked": None}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def now_iso_utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def format_notification(msg):
    sender = msg.get("from", {}).get("emailAddress", {})
    name = sender.get("name") or sender.get("address") or "desconhecido"
    subject = msg.get("subject") or "(sem assunto)"
    preview = (msg.get("bodyPreview") or "").strip().replace("\n", " ")[:120]
    return f"📧 Novo e-mail no Outlook\nDe: {name}\nAssunto: {subject}\n{preview}"


def notify_whatsapp(text, log_fp):
    if not NOTIFY_NUMBER:
        print("ERRO: OUTLOOK_NOTIFY_NUMBER/OPERATOR_NUMBER/TEST_NUMBER ausente ou inválido no .env", file=sys.stderr)
        return False
    ok, _status, _err, _attempts = send_with_retry(NOTIFY_NUMBER, text, None, False, 3, 2, log_fp)
    return ok


def check_new_mail():
    access_token = get_access_token()
    state = load_state()
    since = state.get("last_checked")
    checked_at = now_iso_utc()

    if since is None:
        save_state({"last_checked": checked_at})
        print("✅ primeira checagem — marcando ponto de partida, sem notificar histórico")
        return 0

    query = urllib.parse.urlencode(
        {
            "$filter": f"receivedDateTime ge {since}",
            "$select": "subject,from,receivedDateTime,bodyPreview",
            "$orderby": "receivedDateTime asc",
            "$top": "50",
        }
    )
    data = graph_get(f"/me/mailFolders/inbox/messages?{query}", access_token)
    messages = data.get("value", [])

    LOGS_DIR.mkdir(exist_ok=True)
    log_path = LOGS_DIR / f"outlook_watch_{datetime.now().strftime('%Y%m%d')}.log"
    sent = 0
    with open(log_path, "a", encoding="utf-8") as log_fp:
        for msg in messages:
            if notify_whatsapp(format_notification(msg), log_fp):
                sent += 1

    save_state({"last_checked": checked_at})
    print(f"✅ pull: {len(messages)} e-mail(s) novo(s) · {sent} notificado(s) no WhatsApp")
    return sent


def watch(interval):
    print(f"👀 watch iniciado — checando a cada {interval}s (Ctrl+C pra sair)")
    while True:
        try:
            check_new_mail()
        except Exception as exc:
            print(f"ERRO no ciclo: {type(exc).__name__}: {exc}", file=sys.stderr)
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Monitora Outlook e notifica novo e-mail via WhatsApp")
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("login", help="login interativo (device code), salva token local")
    sub.add_parser("pull", help="checa a caixa de entrada uma vez")
    p_watch = sub.add_parser("watch", help="loop infinito de checagem")
    p_watch.add_argument("--interval", type=int, default=60)

    args = parser.parse_args()
    if args.mode == "login":
        device_code_login()
    elif args.mode == "pull":
        check_new_mail()
    elif args.mode == "watch":
        watch(args.interval)


if __name__ == "__main__":
    main()
