import pytest
from pydantic import ValidationError

from hermes.core.entities import (
    RunHistory,
    Artifact,
    Topic,
    SummaryData,
    JobStatus,
    DailyDigest,
)

def test_run_history_creation():
    rh = RunHistory(
        status="success",
        statusLabel="Sucesso",
        checkpointLabel="Concluído"
    )
    assert rh.status == "success"
    assert rh.startedAtLabel is None

def test_artifact_creation():
    art = Artifact(url="http://example.com/file.pdf", sizeLabel="1.2 MB")
    assert art.url == "http://example.com/file.pdf"
    assert art.sizeLabel == "1.2 MB"

def test_topic_creation():
    topic = Topic(
        title="Test Topic",
        summary="This is a summary",
        impact="High"
    )
    assert topic.signal == "Médio" # default value
    assert topic.impact == "High"

def test_summary_data_defaults():
    sd = SummaryData()
    assert sd.thesis == ""
    assert sd.keyPoints == []
    assert sd.topics == []

def test_job_status_creation():
    js = JobStatus(
        dateRef="2023-10-01",
        status="running",
        statusLabel="Em andamento"
    )
    assert js.dateRef == "2023-10-01"
    assert js.progressPct == 0
    assert js.warnings == []

def test_daily_digest_creation():
    dd = DailyDigest(
        dateRef="2023-10-01",
        dateLabel="01 de Outubro",
        status="completed",
        statusLabel="Concluído"
    )
    assert dd.hasContent is False
    assert dd.pdfCount == 0
    assert dd.audioCount == 0
    assert dd.pdfArtifacts == []
