"""Minimal CLI for the dev kit.

Subcommands:
- print-card    Render the Agent Card for the current env config (useful in CI).
- check-config  Load AppConfig from env and print resolved values.
"""

from __future__ import annotations

import argparse
import json
import sys

from a2a_databricks.card import AgentCard
from a2a_databricks.config import AppConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="a2a-databricks")
    subs = parser.add_subparsers(dest="cmd", required=True)

    p_card = subs.add_parser("print-card", help="Print the Agent Card as JSON.")
    p_card.add_argument(
        "--endpoint-url",
        default="http://localhost:8080",
        help="Public URL where /tasks/send is mounted.",
    )

    subs.add_parser("check-config", help="Print resolved AppConfig values.")

    args = parser.parse_args(argv)

    if args.cmd == "print-card":
        config = AppConfig()
        card = AgentCard.for_config(config, endpoint_url=args.endpoint_url)
        print(card.model_dump_json(indent=2))
        return 0

    if args.cmd == "check-config":
        config = AppConfig()
        print(json.dumps(config.model_dump(mode="json"), indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
