#!/usr/bin/env python3
"""
inbox.py — leitura de mensagens recebidas + classificação + auto-ação

Modos:
  pull       puxa mensagens novas via /chat/messages (ou /messages/list) e popula inbox
  watch      loop infinito: pull a cada N segundos
  webhook    sobe servidor HTTP minimal pra receber webhook da Zappfy
  classify   re-classifica intents do inbox (útil após melhorar regex)
  triage     processa inbox.handled=0: auto-blacklist opt-out, atualiza pipeline,
             responde FAQ simples, envia link de calendly em agendamento
  list       lista inbound recente filtrável por intent
  reply      envia resposta humana a um lead (passa pelo registro de touch)

Auto-ações na triage:
  - opt_out      → adiciona ao blacklist.txt + status=perdido + responde "ok, parei."
  - agendamento  → envia CALENDLY_URL do .env + state=aguardando_reuniao
  - interessado  → status=sql + adiciona tag 'quente' + alerta no stdout
  - objecao_preco→ status=em_conversa + tag 'objecao_preco' + alerta
  - sem_interesse→ status=perdido + tag 'frio'
  - pergunta     → state=em_conversa + alerta pra resposta humana
  - saudacao     → responde "oi {{first_name}}! como posso ajudar?"
  - ruido        → ignora (handled=1, action=ignored)

Webhook:
  POST /webhook/zappfy  body=JSON
  Validação: header X-Zappfy-Token deve bater com WEBHOOK_TOKEN do .env (opcional)

Persistência: SQLite via db.py.
"""

import argparse
import json
import os
import pathlib
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from db import (
    DB_PATH,
    add_to_blacklist_db,
    change_status,
    connect,
    init_db,
    log_inbound,
    log_touch,
    now_iso,
    upsert_lead,
)
from disparo import (
    SCRIPT_DIR,
    api_request,
    load_dotenv,
    normalize_phone_e164_br,
    send_with_retry,
)
from intent import classify

DEFAULT_BLACKLIST = SCRIPT_DIR / "blacklist.txt"
LOGS_DIR = SCRIPT_DIR / "logs"

load_dotenv(SCRIPT_DIR / ".env")
CALENDLY_URL = os.environ.get("CALENDLY_URL", "").strip()
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "").strip()
AUTO_REPLY_OPT_OUT = os.environ.get("AUTO_REPLY_OPT_OUT", "ok, parei. Você não vai mais receber mensagens nossas.")
AUTO_REPLY_AGENDAMENTO_TEMPLATE = os.environ.get(
    "AUTO_REPLY_AGENDAMENTO",
    "Boa! Agenda direto pelo link 👇\n{calendly}\n\nAssim sai certinho no horário que cabe pra você."
)
AUTO_REPLY_SAUDACAO = os.environ.get(
    "AUTO_REPLY_SAUDACAO",
    "oi! tudo bem? Sou da [EMPRESA]. Como posso te ajudar?"
)


def append_blacklist_file(phone_e164, reason=""):
    line = f"{phone_e164}  # auto-blacklist {now_iso()} {reason}".strip()
    DEFAULT_BLACKLIST.parent.mkdir(parents=True, exist_ok=True)
    if DEFAULT_BLACKLIST.is_file():
        existing = DEFAULT_BLACKLIST.read_text(encoding="utf-8")
        digits = "".join(c for c in phone_e164 if c.isdigit())
        if digits in existing:
            return False
    with open(DEFAULT_BLACKLIST, "a", encoding="utf-8") as fp:
        fp.write(line + "\n")
    return True


def fetch_inbox_from_api(since_iso=None, limit=100):
    """Tenta /chat/messages, com fallback para /messages/list. Cada Zappfy varia.
    Operador pode ajustar ENDPOINT_INBOX no .env se necessário."""
    endpoint = os.environ.get("ENDPOINT_INBOX", "/chat/messages")
    params = []
    if since_iso:
        params.append(f"after={since_iso}")
    if limit:
        params.append(f"limit={limit}")
    suffix = ("&" + "&".join(params)) if params else ""
    full = endpoint + suffix
    r = api_request("GET", full)
    if not r["ok"]:
        # Fallback
        endpoint = "/messages/list"
        full = endpoint + suffix
        r = api_request("GET", full)
        if not r["ok"]:
            return None, f"falha em ambos endpoints: {r.get('error', '')}"

    body = r["body"]
    if isinstance(body, dict):
        return body.get("messages", body.get("data", [])), None
    if isinstance(body, list):
        return body, None
    return [], None


def normalize_message(msg):
    """Normaliza mensagem da Zappfy pra dict { id, phone, text, received_at, media_type, raw }.
    Aceita variações de schema."""
    msg_id = msg.get("id") or msg.get("ID") or msg.get("messageId") or msg.get("message_id")
    raw_phone = (
        msg.get("from") or msg.get("From") or
        msg.get("number") or msg.get("Number") or
        msg.get("sender") or msg.get("phone") or ""
    )
    if "@" in str(raw_phone):
        raw_phone = str(raw_phone).split("@", 1)[0]
    phone = normalize_phone_e164_br(raw_phone)
    if not phone:
        return None

    text = (
        msg.get("body") or msg.get("Body") or
        msg.get("text") or msg.get("Text") or
        msg.get("message") or msg.get("caption") or ""
    )

    received = msg.get("timestamp") or msg.get("Timestamp") or msg.get("MessageTimestamp")
    if isinstance(received, (int, float)):
        received_iso = datetime.fromtimestamp(received).replace(microsecond=0).isoformat()
    elif isinstance(received, str):
        received_iso = received
    else:
        received_iso = now_iso()

    media_type = msg.get("type") or msg.get("Type") or "text"
    from_me = msg.get("fromMe") or msg.get("FromMe") or msg.get("from_me") or False
    if from_me:
        return None  # ignora mensagens enviadas pela própria instância

    return {
        "id": str(msg_id) if msg_id else f"{phone}_{received_iso}",
        "phone": phone,
        "text": str(text or ""),
        "received_at": received_iso,
        "media_type": media_type,
        "raw": msg,
    }


def cmd_pull(args):
    init_db()
    since = args.since
    if not since and not args.all:
        # default: últimas 2h se não informar
        from datetime import timedelta
        since = (datetime.now() - timedelta(hours=2)).replace(microsecond=0).isoformat()

    msgs, err = fetch_inbox_from_api(since_iso=since, limit=args.limit)
    if msgs is None:
        print(f"❌ {err}", file=sys.stderr)
        print("Configure ENDPOINT_INBOX no .env ou use o modo webhook.", file=sys.stderr)
        return 1

    inserted = 0
    duplicated = 0
    with connect() as conn:
        for raw_msg in msgs:
            normalized = normalize_message(raw_msg)
            if not normalized:
                continue
            intent, score, _ = classify(normalized["text"])
            upsert_lead(conn, normalized["phone"])
            ok = log_inbound(
                conn,
                message_id=normalized["id"],
                phone_e164=normalized["phone"],
                text=normalized["text"],
                intent=intent,
                intent_score=score,
                received_at=normalized["received_at"],
                media_type=normalized["media_type"],
                raw=json.dumps(normalized["raw"], ensure_ascii=False)[:5000],
            )
            if ok:
                inserted += 1
            else:
                duplicated += 1
    print(f"✅ pull: {inserted} novas | {duplicated} duplicadas | {len(msgs)} total da API")
    return 0


def cmd_watch(args):
    print(f"watch a cada {args.interval}s. Ctrl+C pra parar.")
    while True:
        try:
            cmd_pull(args)
            if args.auto_triage:
                cmd_triage(args)
        except Exception as exc:
            print(f"[watch] erro: {exc}", file=sys.stderr)
        time.sleep(args.interval)


def cmd_classify(args):
    init_db()
    with connect() as conn:
        cur = conn.execute("SELECT id, text FROM inbox")
        updates = []
        for row in cur.fetchall():
            intent, score, _ = classify(row["text"])
            updates.append((intent, score, row["id"]))
        for intent, score, _id in updates:
            conn.execute("UPDATE inbox SET intent = ?, intent_score = ? WHERE id = ?",
                         (intent, score, _id))
    print(f"✅ {len(updates)} mensagens reclassificadas.")
    return 0


def _send_auto_reply(phone, text):
    LOGS_DIR.mkdir(exist_ok=True)
    log_path = LOGS_DIR / f"auto_reply_{datetime.now():%Y-%m-%d}.log"
    with open(log_path, "a", encoding="utf-8") as fp:
        ok, status, err, attempts = send_with_retry(
            phone, text, None, False, retry=2, backoff=2, log_fp=fp
        )
    return ok, status, err


def _render_first_name(conn, phone):
    cur = conn.execute("SELECT first_name FROM leads WHERE phone_e164 = ?", (phone,))
    row = cur.fetchone()
    return row["first_name"] if row and row["first_name"] else ""


def cmd_triage(args):
    init_db()
    with connect() as conn:
        cur = conn.execute(
            "SELECT * FROM inbox WHERE handled = 0 ORDER BY received_at ASC LIMIT ?",
            (args.limit or 500,),
        )
        unhandled = cur.fetchall()

    print(f"triage: {len(unhandled)} mensagens não tratadas")

    actions_count = {}
    for msg in unhandled:
        intent = msg["intent"]
        phone = msg["phone_e164"]
        action = "ignored"
        reply = None

        with connect() as conn:
            if intent == "opt_out":
                appended = append_blacklist_file(phone, "auto-blacklist via inbox")
                add_to_blacklist_db(conn, phone, "opt_out detectado em inbox")
                if not args.no_reply:
                    reply = AUTO_REPLY_OPT_OUT
                action = "blacklist" + (" (file novo)" if appended else " (já existia)")

            elif intent == "agendamento":
                if CALENDLY_URL and not args.no_reply:
                    reply = AUTO_REPLY_AGENDAMENTO_TEMPLATE.format(calendly=CALENDLY_URL)
                conn.execute(
                    "UPDATE conversations SET state = 'aguardando_reuniao', last_state_change = ? WHERE phone_e164 = ?",
                    (now_iso(), phone),
                )
                action = "agendamento" + (" + link enviado" if reply else " (sem CALENDLY_URL no .env)")

            elif intent == "interessado":
                change_status(conn, phone, "sql", "interesse declarado")
                conn.execute(
                    "UPDATE leads SET tags = tags || ',quente', engagement_score = MIN(100, engagement_score + 25), updated_at = ? WHERE phone_e164 = ?",
                    (now_iso(), phone),
                )
                print(f"🔥 LEAD QUENTE: {phone} — \"{msg['text'][:80]}\"")
                action = "promovido_sql"

            elif intent == "objecao_preco":
                change_status(conn, phone, "em_conversa", "objeção de preço")
                conn.execute(
                    "UPDATE leads SET tags = tags || ',objecao_preco', updated_at = ? WHERE phone_e164 = ?",
                    (now_iso(), phone),
                )
                print(f"💰 OBJEÇÃO PREÇO: {phone} — responda manualmente: \"{msg['text'][:80]}\"")
                action = "objecao_preco_alerta"

            elif intent == "sem_interesse":
                change_status(conn, phone, "perdido", "sem interesse declarado")
                action = "marcado_perdido"

            elif intent == "saudacao":
                if not args.no_reply:
                    fname = _render_first_name(conn, phone)
                    msg_reply = AUTO_REPLY_SAUDACAO
                    if fname and "{{first_name}}" in msg_reply:
                        msg_reply = msg_reply.replace("{{first_name}}", fname)
                    reply = msg_reply
                action = "saudacao_respondida"

            elif intent == "pergunta":
                print(f"❓ PERGUNTA: {phone} — \"{msg['text'][:100]}\"")
                action = "alerta_pergunta"

            elif intent == "ruido":
                action = "ignored_ruido"

            else:
                action = "alerta_desconhecido"
                print(f"❔ DESCONHECIDO: {phone} — \"{msg['text'][:80]}\"")

        if reply:
            ok, status, err = _send_auto_reply(phone, reply)
            with connect() as conn:
                log_touch(
                    conn, phone,
                    channel="auto_reply",
                    text=reply,
                    status="ok" if ok else "fail",
                    api_status=status,
                    api_error=err,
                    campaign_id=f"auto_{intent}",
                )

        with connect() as conn:
            conn.execute(
                "UPDATE inbox SET handled = 1, handled_action = ? WHERE id = ?",
                (action, msg["id"]),
            )
        actions_count[action] = actions_count.get(action, 0) + 1

    print("\nResumo da triage:")
    for action, count in sorted(actions_count.items(), key=lambda x: -x[1]):
        print(f"  {count:>4}  {action}")
    return 0


def cmd_list(args):
    init_db()
    with connect() as conn:
        sql = "SELECT * FROM inbox WHERE 1=1"
        params = []
        if args.intent:
            sql += " AND intent = ?"
            params.append(args.intent)
        if args.unhandled:
            sql += " AND handled = 0"
        if args.phone:
            sql += " AND phone_e164 LIKE ?"
            params.append(f"%{args.phone}%")
        sql += " ORDER BY received_at DESC LIMIT ?"
        params.append(args.limit)
        cur = conn.execute(sql, params)
        rows = cur.fetchall()

    print(f"{'PHONE':<16} {'INTENT':<14} {'SCORE':<6} {'HANDLED':<8} {'TEXT':<60}")
    for r in rows:
        text_preview = (r["text"] or "")[:55].replace("\n", " ")
        print(f"{r['phone_e164']:<16} {r['intent']:<14} {r['intent_score']:<6} "
              f"{('sim' if r['handled'] else 'NÃO'):<8} {text_preview}")
    print(f"\n{len(rows)} mensagens.")
    return 0


def cmd_reply(args):
    init_db()
    phone = normalize_phone_e164_br(args.phone)
    if not phone:
        print("ERRO: phone inválido.", file=sys.stderr)
        return 1
    text = pathlib.Path(args.text_file).read_text(encoding="utf-8") if args.text_file else args.text
    if not text:
        print("ERRO: --text ou --text-file.", file=sys.stderr)
        return 1
    LOGS_DIR.mkdir(exist_ok=True)
    log_path = LOGS_DIR / f"reply_{datetime.now():%Y-%m-%d_%H%M%S}.log"
    with open(log_path, "w", encoding="utf-8") as fp:
        ok, status, err, _ = send_with_retry(phone, text, None, False, 2, 2, fp)
    with connect() as conn:
        upsert_lead(conn, phone)
        log_touch(conn, phone, "manual_reply", text,
                  "ok" if ok else "fail", api_status=status, api_error=err)
    print(("✅" if ok else "❌") + f" reply pra {phone} (status={status})")
    return 0 if ok else 1


# ---- Webhook ----

class _WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_POST(self):
        if self.path != "/webhook/zappfy":
            self.send_response(404); self.end_headers(); return

        if WEBHOOK_TOKEN:
            received = self.headers.get("X-Zappfy-Token", "")
            if received != WEBHOOK_TOKEN:
                self.send_response(401); self.end_headers(); return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self.send_response(400); self.end_headers(); return

        msgs = body.get("messages", [body]) if isinstance(body, dict) else body
        if not isinstance(msgs, list):
            msgs = [msgs]

        inserted = 0
        with connect() as conn:
            for raw in msgs:
                norm = normalize_message(raw)
                if not norm:
                    continue
                intent, score, _ = classify(norm["text"])
                upsert_lead(conn, norm["phone"])
                if log_inbound(conn, norm["id"], norm["phone"], norm["text"],
                               intent, score, norm["received_at"], norm["media_type"],
                               json.dumps(norm["raw"], ensure_ascii=False)[:5000]):
                    inserted += 1

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "inserted": inserted}).encode("utf-8"))


def cmd_webhook(args):
    init_db()
    server = HTTPServer((args.host, args.port), _WebhookHandler)
    print(f"Webhook ouvindo em http://{args.host}:{args.port}/webhook/zappfy")
    if WEBHOOK_TOKEN:
        print(f"Header X-Zappfy-Token obrigatório (configurado em .env)")
    print("Configure no painel Zappfy: events=messages.received → URL acima.")
    print("Ctrl+C pra parar.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Inbox + auto-triage de WhatsApp")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("pull", help="puxa mensagens novas via API")
    sp.add_argument("--since", help="ISO datetime (default: -2h)")
    sp.add_argument("--limit", type=int, default=100)
    sp.add_argument("--all", action="store_true", help="todas mensagens (ignora --since)")

    sw = sub.add_parser("watch", help="loop de pull a cada N segundos")
    sw.add_argument("--interval", type=int, default=60)
    sw.add_argument("--limit", type=int, default=100)
    sw.add_argument("--since")
    sw.add_argument("--all", action="store_true")
    sw.add_argument("--auto-triage", action="store_true", help="roda triage após cada pull")

    sub.add_parser("classify", help="reclassifica intents do inbox")

    st = sub.add_parser("triage", help="processa inbound não-tratado")
    st.add_argument("--limit", type=int, default=500)
    st.add_argument("--no-reply", action="store_true", help="não envia auto-replies, só atualiza pipeline")

    sl = sub.add_parser("list", help="lista inbound")
    sl.add_argument("--intent")
    sl.add_argument("--phone")
    sl.add_argument("--unhandled", action="store_true")
    sl.add_argument("--limit", type=int, default=50)

    sr = sub.add_parser("reply", help="envia resposta humana 1:1")
    sr.add_argument("--phone", required=True)
    sr.add_argument("--text")
    sr.add_argument("--text-file")

    sweb = sub.add_parser("webhook", help="sobe servidor HTTP pra receber eventos da Zappfy")
    sweb.add_argument("--host", default="0.0.0.0")
    sweb.add_argument("--port", type=int, default=8765)
    return p


def main():
    args = build_parser().parse_args()
    return {
        "pull":     cmd_pull,
        "watch":    cmd_watch,
        "classify": cmd_classify,
        "triage":   cmd_triage,
        "list":     cmd_list,
        "reply":    cmd_reply,
        "webhook":  cmd_webhook,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
