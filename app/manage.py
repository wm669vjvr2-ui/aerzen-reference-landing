"""Operator-only data export, deletion and optional retention: no public admin route."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from .config import Settings
from .database import Store


def main():
    parser=argparse.ArgumentParser(description="Local, operator-only data maintenance")
    sub=parser.add_subparsers(dest="command",required=True)
    listing=sub.add_parser("list"); listing.add_argument("--kind",choices=["leads","orders"],default="leads"); listing.add_argument("--limit",type=int,default=20)
    export=sub.add_parser("export"); export.add_argument("id"); export.add_argument("--output",type=Path,required=True)
    delete=sub.add_parser("delete"); delete.add_argument("id"); delete.add_argument("--confirm",action="store_true",required=True)
    purge=sub.add_parser("purge",aliases=["prune"]); purge.add_argument("--days",type=int,required=True); purge.add_argument("--confirm",action="store_true",required=True)
    args=parser.parse_args()
    settings=Settings(); store=Store(settings.data_dir)
    if args.command=="list":
        if not 1<=args.limit<=100: parser.error("Limit must be between 1 and 100")
        with store.connect() as db:
            rows=db.execute(f"SELECT id,created_at FROM {args.kind} ORDER BY created_at DESC LIMIT ?",(args.limit,)).fetchall()
        for row in rows: print(json.dumps(dict(row)))
    elif args.command=="export":
        target=args.output.resolve()
        if (settings.root_dir/"static") in target.parents:
            parser.error("Export must not be under public static files")
        with store.connect() as db:
            rows={table:[dict(row) for row in db.execute(f"SELECT * FROM {table} WHERE id=?",(args.id,))] for table in ("leads","orders")}
        if not any(rows.values()): parser.error("Record not found")
        descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,"w",encoding="utf-8") as handle: json.dump(rows,handle,ensure_ascii=False,indent=2)
        print("Export completed")
    elif args.command=="delete":
        with store.connect() as db:
            db.execute("DELETE FROM leads WHERE id=?",(args.id,))
            db.execute("DELETE FROM orders WHERE id=?",(args.id,))
        print("Deletion completed; review any operator-managed backups separately")
    else:
        if not 1<=args.days<=3650: parser.error("Set an approved retention period between 1 and 3650 days")
        cutoff=int(time.time())-args.days*86400
        with store.connect() as db:
            db.execute("DELETE FROM leads WHERE created_at<?",(cutoff,))
            # Orders can require legal retention; they are never automatically purged with leads.
        print("Lead retention applied; no order records were deleted")


if __name__=="__main__":
    main()
