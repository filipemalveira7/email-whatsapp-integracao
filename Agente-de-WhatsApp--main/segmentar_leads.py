#!/usr/bin/env python3
"""
segmentar_leads.py — filtra leads de um CSV por critérios

Critérios:
  --min-groups N        presente em pelo menos N grupos (cross-grupo dedup)
  --only-admin          só admins
  --ddd 11,21,31        só estes DDDs
  --name-contains termo nome contém termo (case-insensitive)
  --exclude-blacklist   remove números em blacklist.txt
  --exclude-csv path    remove números presentes em outro CSV
"""

import argparse
import csv
import pathlib
import re
import sys

from disparo import DEFAULT_BLACKLIST, load_blacklist


def parse_ddds(value):
    if not value:
        return None
    return {int(d.strip()) for d in value.split(",") if d.strip().isdigit()}


def extract_ddd(phone_e164):
    digits = re.sub(r"\D", "", phone_e164 or "")
    if digits.startswith("55") and len(digits) >= 12:
        return int(digits[2:4])
    if len(digits) >= 10:
        return int(digits[:2])
    return None


def load_exclude_csv(path):
    if not path:
        return set()
    p = pathlib.Path(path).expanduser()
    if not p.is_file():
        print(f"⚠️ exclude-csv não existe: {p}", file=sys.stderr)
        return set()
    nums = set()
    with open(p, "r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            phone = row.get("lead_phone_e164") or row.get("phone") or ""
            digits = re.sub(r"\D", "", phone)
            if digits:
                nums.add(digits)
    return nums


def main():
    p = argparse.ArgumentParser(description="Segmenta leads por critério")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--min-groups", type=int, default=0)
    p.add_argument("--only-admin", action="store_true")
    p.add_argument("--ddd", help="lista CSV: 11,21,31")
    p.add_argument("--name-contains")
    p.add_argument("--exclude-blacklist", action="store_true")
    p.add_argument("--exclude-csv")
    p.add_argument("--blacklist", default=str(DEFAULT_BLACKLIST))
    args = p.parse_args()

    inp = pathlib.Path(args.input).expanduser()
    if not inp.is_file():
        print(f"ERRO: input não encontrado: {inp}", file=sys.stderr)
        return 1

    ddds = parse_ddds(args.ddd)
    blacklist = load_blacklist(args.blacklist) if args.exclude_blacklist else set()
    exclude_set = load_exclude_csv(args.exclude_csv)

    total = 0
    kept = 0
    out = pathlib.Path(args.output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(inp, "r", encoding="utf-8", newline="") as src:
        reader = csv.DictReader(src)
        fieldnames = reader.fieldnames
        with open(out, "w", encoding="utf-8", newline="") as dst:
            writer = csv.DictWriter(dst, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                total += 1
                phone = row.get("lead_phone_e164") or row.get("phone") or ""
                digits = re.sub(r"\D", "", phone)
                if not digits:
                    continue
                if blacklist and digits in blacklist:
                    continue
                if exclude_set and digits in exclude_set:
                    continue
                gc = int(row.get("group_count", 1) or 1)
                if args.min_groups and gc < args.min_groups:
                    continue
                if args.only_admin:
                    is_admin = str(row.get("is_admin", "")).lower() in ("true", "1", "yes", "sim")
                    is_super = str(row.get("is_super_admin", "")).lower() in ("true", "1", "yes", "sim")
                    if not (is_admin or is_super):
                        continue
                if ddds:
                    ddd = extract_ddd(phone)
                    if ddd not in ddds:
                        continue
                if args.name_contains:
                    name = (row.get("lead_display_name") or "").lower()
                    if args.name_contains.lower() not in name:
                        continue
                writer.writerow(row)
                kept += 1

    pct = (kept / total * 100) if total else 0
    print(f"✅ {total} → {kept} leads ({pct:.1f}% qualificados)")
    print(f"Output: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
