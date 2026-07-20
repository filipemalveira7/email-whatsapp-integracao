#!/usr/bin/env python3
"""
pipeline.py — kanban CLI + forecast ponderado

7 estágios (db.PIPELINE_STAGES):
  novo · mql · sql · em_conversa · proposta · negociacao · ganho · perdido

Comandos:
  show              kanban visual (colunas com leads)
  move              move lead manualmente: --phone --to <stage>
  forecast          forecast ponderado por probabilidade × ticket
  funnel            funil com taxa de conversão entre estágios
  audit             encontra leads "abandonados" (sem touch há N dias)
  promote           promove leads automaticamente: alta engagement → mql; opt-in declarado → sql
  export            CSV de todos os leads ativos
"""

import argparse
import csv
import os
import pathlib
import sys
from datetime import datetime, timedelta

from db import (
    PIPELINE_PROBABILITY,
    PIPELINE_STAGES,
    change_status,
    connect,
    init_db,
    now_iso,
)
from disparo import SCRIPT_DIR, load_dotenv

load_dotenv(SCRIPT_DIR / ".env")
DEFAULT_TICKET = float(os.environ.get("DEFAULT_TICKET", "1000"))


def cmd_show(args):
    init_db()
    cols = {s: [] for s in PIPELINE_STAGES if s != "perdido"}
    with connect() as conn:
        cur = conn.execute(
            "SELECT phone_e164, name, fit_score, engagement_score, status, last_inbound_at, last_outbound_at, tags "
            "FROM leads WHERE status != 'perdido' ORDER BY fit_score DESC LIMIT ?",
            (args.limit,),
        )
        for r in cur.fetchall():
            if r["status"] in cols:
                cols[r["status"]].append(r)

    print("═" * 110)
    print("KANBAN — pipeline ativo")
    print("═" * 110)
    for stage in PIPELINE_STAGES:
        if stage == "perdido":
            continue
        leads = cols.get(stage, [])
        prob = PIPELINE_PROBABILITY.get(stage, 0)
        print(f"\n▮ {stage.upper()}  ({len(leads)} leads · prob {int(prob*100)}%)")
        for lead in leads[:args.per_column]:
            name = (lead["name"] or "(sem nome)")[:24]
            phone = lead["phone_e164"][-9:]
            print(f"  · {name:<26} ...{phone}  fit={lead['fit_score']:>3}  eng={lead['engagement_score']:>3}  {lead['tags'][:30]}")
        if len(leads) > args.per_column:
            print(f"   (+ {len(leads) - args.per_column} mais)")
    print("\n" + "═" * 110)
    return 0


def cmd_move(args):
    init_db()
    from disparo import normalize_phone_e164_br
    phone = normalize_phone_e164_br(args.phone)
    if not phone:
        print("ERRO: phone inválido.", file=sys.stderr)
        return 1
    if args.to not in PIPELINE_STAGES:
        print(f"ERRO: status inválido. Use: {', '.join(PIPELINE_STAGES)}", file=sys.stderr)
        return 1
    with connect() as conn:
        moved = change_status(conn, phone, args.to, args.reason or "manual")
    print(("✅ movido" if moved else "⚠️ já estava nesse status") + f": {phone} → {args.to}")
    return 0


def cmd_forecast(args):
    init_db()
    ticket = args.ticket or DEFAULT_TICKET
    print(f"Forecast ponderado (ticket médio R$ {ticket:,.2f})")
    print("─" * 80)
    print(f"{'STAGE':<14} {'LEADS':<7} {'PROB':<6} {'PIPELINE R$':<18} {'PONDERADO R$':<18}")
    total_pipeline = 0
    total_weighted = 0
    with connect() as conn:
        for stage in PIPELINE_STAGES:
            if stage in ("perdido", "ganho"):
                continue
            cur = conn.execute("SELECT COUNT(*) AS n FROM leads WHERE status = ?", (stage,))
            n = cur.fetchone()["n"]
            prob = PIPELINE_PROBABILITY.get(stage, 0)
            pipeline = n * ticket
            weighted = pipeline * prob
            total_pipeline += pipeline
            total_weighted += weighted
            print(f"{stage:<14} {n:<7} {int(prob*100):<5}% R$ {pipeline:>14,.0f}  R$ {weighted:>14,.0f}")

        cur = conn.execute("SELECT COUNT(*) AS n FROM leads WHERE status = 'ganho'")
        ganhos = cur.fetchone()["n"]
        receita_real = ganhos * ticket

    print("─" * 80)
    print(f"{'PIPELINE TOTAL':<27} R$ {total_pipeline:>14,.0f}")
    print(f"{'PROJEÇÃO PONDERADA':<27} R$ {total_weighted:>14,.0f}")
    print(f"{'GANHO REALIZADO':<27} R$ {receita_real:>14,.0f}  ({ganhos} fechamentos)")
    print(f"{'PROJEÇÃO + REAL':<27} R$ {(total_weighted + receita_real):>14,.0f}")
    return 0


def cmd_funnel(args):
    init_db()
    print("Funil de conversão")
    print("─" * 60)
    counts = {}
    with connect() as conn:
        for stage in PIPELINE_STAGES:
            cur = conn.execute("SELECT COUNT(*) AS n FROM leads WHERE status = ?", (stage,))
            counts[stage] = cur.fetchone()["n"]
        cur = conn.execute("""
            SELECT to_status, COUNT(DISTINCT phone_e164) AS n FROM pipeline_events
            GROUP BY to_status
        """)
        ever = {r["to_status"]: r["n"] for r in cur.fetchall()}

    base_funnel = ["novo", "mql", "sql", "em_conversa", "proposta", "negociacao", "ganho"]
    for i, stage in enumerate(base_funnel):
        ever_n = ever.get(stage, counts.get(stage, 0))
        active = counts.get(stage, 0)
        if i == 0:
            print(f"{stage:<14} {ever_n:>6} (já passaram)  {active:>6} ativos")
            prev = ever_n or 1
        else:
            conv = (ever_n / prev * 100) if prev else 0
            print(f"{stage:<14} {ever_n:>6} (já passaram)  {active:>6} ativos   conv {conv:.1f}%")
            prev = ever_n or 1
    print("─" * 60)
    return 0


def cmd_audit(args):
    init_db()
    cutoff = (datetime.now() - timedelta(days=args.days)).isoformat()
    with connect() as conn:
        cur = conn.execute("""
            SELECT phone_e164, name, status, fit_score, last_outbound_at, last_inbound_at, touches_count
            FROM leads
            WHERE status NOT IN ('perdido', 'ganho')
              AND (last_outbound_at IS NULL OR last_outbound_at < ?)
            ORDER BY fit_score DESC
            LIMIT ?
        """, (cutoff, args.limit))
        rows = cur.fetchall()
    print(f"Leads sem toque há ≥{args.days} dias ({len(rows)}):")
    print(f"{'PHONE':<16} {'NOME':<22} {'STATUS':<13} {'FIT':<5} {'LAST_OUT':<20} {'LAST_IN':<20}")
    for r in rows:
        name = (r["name"] or "")[:20]
        last_out = (r["last_outbound_at"] or "nunca")[:19]
        last_in = (r["last_inbound_at"] or "—")[:19]
        print(f"{r['phone_e164']:<16} {name:<22} {r['status']:<13} {r['fit_score']:<5} {last_out:<20} {last_in:<20}")
    return 0


def cmd_promote(args):
    init_db()
    promoted = 0
    with connect() as conn:
        cur = conn.execute("""
            SELECT phone_e164 FROM leads
            WHERE status = 'novo' AND engagement_score >= ?
        """, (args.engagement_threshold,))
        for r in cur.fetchall():
            change_status(conn, r["phone_e164"], "mql", f"engagement >= {args.engagement_threshold}")
            promoted += 1
        cur = conn.execute("""
            SELECT phone_e164 FROM leads
            WHERE status IN ('novo', 'mql')
              AND fit_score >= ?
        """, (args.fit_threshold,))
        for r in cur.fetchall():
            change_status(conn, r["phone_e164"], "sql", f"fit >= {args.fit_threshold}")
            promoted += 1
    print(f"✅ {promoted} promoções aplicadas.")
    return 0


def cmd_export(args):
    init_db()
    out = pathlib.Path(args.output).expanduser()
    with connect() as conn:
        cur = conn.execute(
            "SELECT phone_e164, name, status, fit_score, engagement_score, "
            "last_intent, last_outbound_at, last_inbound_at, touches_count, "
            "replies_count, tags, source FROM leads WHERE status != 'perdido' OR ? = 1",
            (1 if args.include_lost else 0,),
        )
        rows = cur.fetchall()
    if not rows:
        print("Nenhum lead.")
        return 0
    fields = list(rows[0].keys())
    with open(out, "w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r[k] for k in fields})
    print(f"✅ {len(rows)} leads exportados em {out}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Pipeline kanban + forecast")
    sub = p.add_subparsers(dest="cmd", required=True)

    ss = sub.add_parser("show")
    ss.add_argument("--limit", type=int, default=500)
    ss.add_argument("--per-column", type=int, default=10)

    sm = sub.add_parser("move")
    sm.add_argument("--phone", required=True)
    sm.add_argument("--to", required=True, choices=PIPELINE_STAGES)
    sm.add_argument("--reason")

    sf = sub.add_parser("forecast")
    sf.add_argument("--ticket", type=float)

    sub.add_parser("funnel")

    sa = sub.add_parser("audit")
    sa.add_argument("--days", type=int, default=14)
    sa.add_argument("--limit", type=int, default=100)

    sp = sub.add_parser("promote")
    sp.add_argument("--engagement-threshold", type=int, default=30)
    sp.add_argument("--fit-threshold", type=int, default=70)

    se = sub.add_parser("export")
    se.add_argument("--output", required=True)
    se.add_argument("--include-lost", action="store_true")

    return p


def main():
    args = build_parser().parse_args()
    return {
        "show":     cmd_show,
        "move":     cmd_move,
        "forecast": cmd_forecast,
        "funnel":   cmd_funnel,
        "audit":    cmd_audit,
        "promote":  cmd_promote,
        "export":   cmd_export,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
