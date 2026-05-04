from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from hermes.infra.adapters.state_repository import SqliteStateRepository
from hermes.use_cases.process_daily import ProcessDailyUseCase
from hermes.use_cases.send_to_kindle import SendToKindleUseCase


os.makedirs("data/pdf", exist_ok=True)
os.makedirs("data/audio", exist_ok=True)

app = FastAPI(title="Hermes Web Dashboard")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "web", "static")),
    name="static",
)
app.mount(
    "/artifacts/pdf",
    StaticFiles(directory=os.path.join(os.getcwd(), "data/pdf")),
    name="pdf",
)
app.mount(
    "/artifacts/audio",
    StaticFiles(directory=os.path.join(os.getcwd(), "data/audio")),
    name="audio",
)


PT_WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
PT_MONTHS = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


@dataclass
class ServerConfig:
    state_repo: SqliteStateRepository | None = None
    process_daily_uc: ProcessDailyUseCase | None = None
    send_to_kindle_uc: SendToKindleUseCase | None = None
    days_back: int = 28
    default_kindle_email: str = ""
    kindle_enabled: bool = False


class GenerateRequest(BaseModel):
    date_ref: str
    force: bool = False


class KindleRequest(BaseModel):
    date_ref: str
    kindle_email: Optional[str] = None


def _pt_date_label(day: datetime) -> str:
    weekday = PT_WEEKDAYS[day.weekday()]
    month = PT_MONTHS[day.month - 1]
    return f"{weekday}, {day.day} de {month}"


def _relative_label(day: datetime, today: datetime) -> str:
    delta = (today.date() - day.date()).days
    if delta == 0:
        return "Hoje"
    if delta == 1:
        return "Ontem"
    return f"{PT_WEEKDAYS[day.weekday()].capitalize()} · {day.day:02d}/{day.month:02d}"


def _decorate_entry(date_ref: str, digest: Optional[dict], today: datetime) -> dict:
    day = datetime.strptime(date_ref, "%Y-%m-%d")
    base = digest or {
        "dateRef": date_ref,
        "status": "missing",
        "statusLabel": "Pendente",
        "hasContent": False,
        "pdfCount": 0,
        "audioCount": 0,
        "warnings": [],
    }

    base["dateRef"] = date_ref
    base["dateLabel"] = _relative_label(day, today)
    base["fullDateLabel"] = _pt_date_label(day)
    base["shortWeekday"] = PT_WEEKDAYS[day.weekday()][:3].upper()
    base["dayNumber"] = f"{day.day:02d}"
    base["monthShort"] = PT_MONTHS[day.month - 1][:3].capitalize()
    base["isToday"] = day.date() == today.date()
    base["isPending"] = base.get("status") in {"missing", "idle"}
    return base


def _build_calendar_weeks(entries: list[dict]) -> list[dict]:
    week_buckets: dict[str, list[dict]] = {}
    for entry in sorted(entries, key=lambda item: item["dateRef"]):
        day = datetime.strptime(entry["dateRef"], "%Y-%m-%d")
        monday = (day - timedelta(days=day.weekday())).strftime("%Y-%m-%d")
        week_buckets.setdefault(monday, []).append(entry)

    weeks = []
    for monday_ref in sorted(week_buckets.keys(), reverse=True):
        days = sorted(
            week_buckets[monday_ref], key=lambda item: item["dateRef"], reverse=True
        )
        monday = datetime.strptime(monday_ref, "%Y-%m-%d")
        sunday = monday + timedelta(days=6)
        weeks.append(
            {
                "weekRef": monday_ref,
                "label": f"{monday.day:02d} {PT_MONTHS[monday.month - 1][:3]} - {sunday.day:02d} {PT_MONTHS[sunday.month - 1][:3]}",
                "days": days,
            }
        )
    return weeks


def _build_stats(entries: list[dict]) -> dict:
    ready = sum(1 for entry in entries if entry.get("status") in {"ready", "succeeded"})
    running = sum(
        1 for entry in entries if entry.get("status") in {"running", "queued"}
    )
    pending = sum(1 for entry in entries if entry.get("status") in {"missing", "idle"})
    return {
        "ready": ready,
        "running": running,
        "pending": pending,
    }


def get_overview_data(days_back: int, selected_date: Optional[str] = None):
    if ServerConfig.state_repo is None:
        raise RuntimeError("State repository not configured")

    today = datetime.now()
    entries: list[dict] = []

    for offset in range(days_back):
        day = today - timedelta(days=offset)
        date_ref = day.strftime("%Y-%m-%d")
        digest = ServerConfig.state_repo.get_digest(date_ref)
        entries.append(_decorate_entry(date_ref, digest, today))

    selected_date = selected_date or today.strftime("%Y-%m-%d")
    selected_entry = next(
        (entry for entry in entries if entry["dateRef"] == selected_date), None
    )
    if selected_entry is None:
        selected_entry = _decorate_entry(
            selected_date, ServerConfig.state_repo.get_digest(selected_date), today
        )
    selected_job = (
        ServerConfig.state_repo.get_job(selected_date) if selected_date else None
    )

    return {
        "daysBack": days_back,
        "selectedDate": selected_date,
        "generatedAtLabel": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "entries": entries,
        "calendarWeeks": _build_calendar_weeks(entries),
        "stats": _build_stats(entries),
        "selectedEntry": selected_entry,
        "selectedJob": selected_job,
        "kindle": {
            "configured": ServerConfig.kindle_enabled,
            "defaultEmail": ServerConfig.default_kindle_email,
        },
    }


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, days: int | None = None, date: str | None = None):
    days_back = days or ServerConfig.days_back
    overview_data = get_overview_data(days_back, date)
    templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html.j2",
        context={
            "page_title": "Hermes",
            "state_payload": overview_data,
        },
    )


@app.get("/api/overview")
async def api_overview(days: int | None = None, date: str | None = None):
    return get_overview_data(days or ServerConfig.days_back, date)


@app.get("/api/days/{date_ref}")
async def api_day(date_ref: str):
    if ServerConfig.state_repo is None:
        raise RuntimeError("State repository not configured")

    today = datetime.now()
    entry = _decorate_entry(
        date_ref, ServerConfig.state_repo.get_digest(date_ref), today
    )
    job = ServerConfig.state_repo.get_job(date_ref)
    return {
        "entry": entry,
        "job": job,
        "kindle": {
            "configured": ServerConfig.kindle_enabled,
            "defaultEmail": ServerConfig.default_kindle_email,
        },
    }


@app.post("/api/generate")
async def api_generate(req: GenerateRequest):
    if ServerConfig.state_repo is None or ServerConfig.process_daily_uc is None:
        raise RuntimeError("Server not configured")

    existing_job = ServerConfig.state_repo.get_job(req.date_ref)
    if (
        existing_job
        and existing_job.get("status") in {"queued", "running"}
        and not req.force
    ):
        entry = _decorate_entry(
            req.date_ref,
            ServerConfig.state_repo.get_digest(req.date_ref),
            datetime.now(),
        )
        return {"entry": entry, "job": existing_job}

    queued_job = {
        "dateRef": req.date_ref,
        "status": "queued",
        "statusLabel": "Na fila",
        "message": "Execução enfileirada e aguardando início.",
        "progressPct": 3,
        "currentStepKey": "queued",
        "currentStepLabel": "Aguardando execução",
        "warnings": [],
    }
    ServerConfig.state_repo.save_job(req.date_ref, queued_job)

    asyncio.create_task(ServerConfig.process_daily_uc.execute(req.date_ref, req.force))

    entry = _decorate_entry(
        req.date_ref, ServerConfig.state_repo.get_digest(req.date_ref), datetime.now()
    )
    return {"entry": entry, "job": queued_job}


@app.post("/api/kindle/send")
async def api_send_kindle(req: KindleRequest):
    if ServerConfig.send_to_kindle_uc is None:
        raise HTTPException(
            status_code=400,
            detail="O envio para Kindle não está disponível nesta instalação.",
        )

    try:
        result = ServerConfig.send_to_kindle_uc.execute(req.date_ref, req.kindle_email)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result
