"""Janela de recuperação de candidatas, independente do tema do dia."""
from datetime import datetime, timedelta


def collection_start(now: datetime, last_completed: str | None, initial_days: int = 7, recovery_days: int = 7) -> tuple[datetime, str]:
    if now.tzinfo is None or not 1 <= initial_days <= 30 or not 1 <= recovery_days <= 30:
        raise ValueError("Use horário com fuso e janelas de 1 a 30 dias")
    if last_completed is None:
        return now - timedelta(days=initial_days), "janela inicial: ainda não há edição concluída"
    last = datetime.fromisoformat(last_completed)
    if last.tzinfo is None or last > now:
        raise ValueError("Última edição deve ter fuso e não estar no futuro")
    # Pequena sobreposição protege limites; duplicação será tratada separadamente.
    requested = last - timedelta(hours=1)
    floor = now - timedelta(days=recovery_days)
    return max(requested, floor), ("recuperação limitada; pode haver lacuna" if requested < floor else "desde a última edição concluída, com 1h de sobreposição")
