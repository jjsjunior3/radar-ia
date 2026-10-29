"""Entrada publica: producao acompanhada ou coleta local sem servicos pagos."""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from .collection import collect_sources
from .production import read_json, write_json


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == 'production':
        from .production_cli import main as production_main
        return production_main(args[1:])
    parser = argparse.ArgumentParser(description='Radar IA privado; use production --help para o fluxo acompanhado')
    parser.add_argument('--preview', action='store_true', help='Coleta RSS sem LLM/AWS; nao consulta historico remoto')
    options = parser.parse_args(args)
    if not options.preview:
        parser.print_help()
        return
    load_dotenv()
    now = datetime.now(timezone.utc)
    sources = read_json(Path(os.getenv('RSS_SOURCES_FILE','config/sources.json')))
    report = collect_sources(sources, now, now-timedelta(days=7))
    target = Path(os.getenv('OUTPUT_DIR','local-output'))/'preview'/'coleta.json'
    write_json(target,report)
    print('Candidatas:',len(report['candidates']),'| Arquivo:',target.resolve())


if __name__ == '__main__':main()
