from typing import List, Optional

from pydantic import BaseModel, Field


class RunHistory(BaseModel):
    status: str
    statusLabel: str
    checkpointLabel: str
    startedAtLabel: Optional[str] = None


class Artifact(BaseModel):
    url: str
    sizeLabel: str


class Topic(BaseModel):
    title: str
    summary: str
    impact: str
    signal: str = "Médio"


class SummaryData(BaseModel):
    thesis: str = ""
    executiveSummary: str = ""
    keyPoints: List[str] = Field(default_factory=list)
    topics: List[Topic] = Field(default_factory=list)
    closing: str = ""
    rawMarkdown: Optional[str] = None
    plainText: str = ""
    ttsScript: str = ""
    sourceCount: int = 0
    paragraphCount: int = 0


class JobStatus(BaseModel):
    dateRef: str
    status: str
    statusLabel: str
    message: Optional[str] = None
    error: Optional[str] = None
    progressPct: int = 0
    currentStepKey: Optional[str] = None
    currentStepLabel: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class DailyDigest(BaseModel):
    dateRef: str
    dateLabel: str
    status: str
    statusLabel: str
    hasContent: bool = False
    summary: Optional[str] = None
    summaryData: Optional[SummaryData] = None
    pdfCount: int = 0
    audioCount: int = 0
    pdfArtifacts: List[Artifact] = Field(default_factory=list)
    audioArtifacts: List[Artifact] = Field(default_factory=list)
    runHistory: List[RunHistory] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
