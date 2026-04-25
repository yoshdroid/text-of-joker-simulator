from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import bootstrap
from .match import MatchBootstrapResult


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A.C.T.I.S. bootstrap CLI")
    parser.add_argument(
        "--cardpool",
        default="text-of-joker.cardpool.xlsx",
        help="Path to cardpool xlsx",
    )
    parser.add_argument(
        "--regulation",
        default="configs/regulation.default.json",
        help="Path to regulation json",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print bootstrap summary only",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    context = bootstrap(Path(args.cardpool), Path(args.regulation))
    print(
        json.dumps(
            {
                "status": "ok",
                "card_count": len(context.cardpool),
                "round_count": context.regulation.round_count,
                "summary_only": args.summary_only,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
