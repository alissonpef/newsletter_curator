from __future__ import annotations

import asyncio
import sys
from datetime import datetime

from dotenv import load_dotenv

from hermes.infra.container import build_container


async def run_cli(date_ref: str):
    load_dotenv()

    container = build_container()

    print(f"--- Iniciando Processamento para {date_ref} ---")
    await container.process_daily_uc.execute(date_ref, force=True)
    print(f"--- Processamento para {date_ref} Finalizado ---")


def main():
    if len(sys.argv) > 1 and sys.argv[1]:
        date_str = sys.argv[1]
        try:
            if "/" in date_str:
                parts = date_str.split("/")
                if len(parts[2]) == 2:
                    parts[2] = "20" + parts[2]
                dt = datetime.strptime(f"{parts[2]}-{parts[1]}-{parts[0]}", "%Y-%m-%d")
                date_ref = dt.strftime("%Y-%m-%d")
            else:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                date_ref = dt.strftime("%Y-%m-%d")
        except Exception:
            print(f"Erro: Formato de data inválido '{date_str}'. Use DD/MM/YY ou YYYY-MM-DD.")
            sys.exit(1)
    else:
        date_ref = datetime.now().strftime("%Y-%m-%d")

    asyncio.run(run_cli(date_ref))


if __name__ == "__main__":
    main()
