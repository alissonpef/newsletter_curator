from datetime import date

from ...core.entities import RunState
from ...ports.state_store_port import StateStorePort


class PersistRunStateUseCase:
    def __init__(self, state_store: StateStorePort, clock, logger) -> None:
        self._state_store = state_store
        self._clock = clock
        self._logger = logger
        self._run_started_at: dict[str, object] = {}

    def start(self, run_id: str, date_ref: date) -> RunState:
        started_at = self._clock.now_utc()
        self._state_store.start_run(run_id, date_ref)
        self._run_started_at[run_id] = started_at
        state = RunState(
            run_id=run_id,
            status="running",
            started_at=started_at,
            finished_at=None,
            checkpoint="started",
        )
        self._logger.info("run started", extra={"run_id": run_id, "date_ref": date_ref.isoformat()})
        return state

    def checkpoint(self, run_id: str, checkpoint: str, status: str = "running") -> RunState:
        started_at = self._run_started_at.get(run_id)
        if started_at is None:
            started_at = self._clock.now_utc()
            self._run_started_at[run_id] = started_at

        self._state_store.update_run_status(run_id, status, checkpoint)
        state = RunState(
            run_id=run_id,
            status=status,
            started_at=started_at,
            finished_at=None,
            checkpoint=checkpoint,
        )
        self._logger.info("run checkpoint", extra={"run_id": run_id, "checkpoint": checkpoint})
        return state

    def finish(self, run_id: str, status: str, error: str | None = None) -> RunState:
        started_at = self._run_started_at.get(run_id)
        if started_at is None:
            started_at = self._clock.now_utc()

        finished_at = self._clock.now_utc()
        self._state_store.finish_run(run_id, status, error)
        state = RunState(
            run_id=run_id,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            checkpoint="finished",
        )
        self._logger.info("run finished", extra={"run_id": run_id, "status": status})
        return state

    def recover_missed_dates(self, days_back: int) -> list[date]:
        return self._state_store.get_missed_run_dates(days_back)
