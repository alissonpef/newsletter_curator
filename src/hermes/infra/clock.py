from datetime import datetime, date, timezone


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def today_local(self) -> date:
        return datetime.now().astimezone().date()
