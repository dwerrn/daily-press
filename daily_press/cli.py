"""Command-line entry point for scheduled and operator-triggered generation."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
import json

from daily_press.config import load_settings
from daily_press.generator import EditionGenerator, GenerationInProgress


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily-press")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="generate and archive an edition")
    generate.add_argument("--date", dest="edition_date", type=date.fromisoformat)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "generate":
        return 2
    try:
        result = asyncio.run(EditionGenerator(load_settings()).generate(args.edition_date))
    except GenerationInProgress as error:
        print(str(error))
        return 2
    except Exception as error:
        print(f"generation failed: {type(error).__name__}")
        return 1
    print(json.dumps(result.public_dict(), sort_keys=True))
    return 0
