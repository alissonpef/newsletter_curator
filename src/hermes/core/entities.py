from pydantic import BaseModel, Field


class RunHistory(BaseModel):
    status: str
    statusLabel: str
    checkpointLabel: str
    startedAtLabel: str | None = None


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
    keyPoints: list[str] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    closing: str = ""
    rawMarkdown: str | None = None
    plainText: str = ""
    ttsScript: str = ""
    sourceCount: int = 0
    paragraphCount: int = 0


class JobStatus(BaseModel):
    dateRef: str
    status: str
    statusLabel: str
    message: str | None = None
    error: str | None = None
    progressPct: int = 0
    currentStepKey: str | None = None
    currentStepLabel: str | None = None
    warnings: list[str] = Field(default_factory=list)


class DailyDigest(BaseModel):
    dateRef: str
    dateLabel: str
    status: str
    statusLabel: str
    hasContent: bool = False
    summary: str | None = None
    summaryData: SummaryData | None = None
    pdfCount: int = 0
    audioCount: int = 0
    pdfArtifacts: list[Artifact] = Field(default_factory=list)
    audioArtifacts: list[Artifact] = Field(default_factory=list)
    runHistory: list[RunHistory] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
