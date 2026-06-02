# -*- coding: utf-8 -*-
"""Data models for the PDF Process Analysis System."""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ProcessStep:
    """A single process step in manufacturing."""

    tag: str  # 标签编码
    content: str  # 工序内容
    factory: str = ""  # 分厂
    specialty: str = ""  # 专业类型
    description: str = ""  # 工序描述
    workcenter: str = ""  # 工作中心
    operation_time: str = ""  # 操作时间
    prep_time: str = ""  # 准备时间
    base_count: str = ""  # 工时基准件数
    status: str = ""  # 工序状态

    @classmethod
    def from_list(cls, data: List[str]) -> "ProcessStep":
        """Create from list [tag, content, ...]."""
        return cls(
            tag=data[0] if len(data) > 0 else "",
            content=data[1] if len(data) > 1 else "",
        )

    def to_list(self) -> List[str]:
        """Convert to list for display."""
        return [
            self.tag,
            self.content,
        ]


@dataclass
class ProcessFlow:
    """Container for process flow data."""

    raw: str = ""
    data: List[ProcessStep] = field(default_factory=list)
    columns: List[str] = field(default_factory=lambda: ["标签编码", "工序内容"])
    format: str = "markdown"
    tables: Optional[Dict[str, List[List[str]]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw": self.raw,
            "data": [[s.tag, s.content] for s in self.data],
            "columns": self.columns,
            "format": self.format,
        }


@dataclass
class VisionResult:
    """Result from vision analysis of a single page."""

    image_path: str
    description: str
    timestamp: str = ""


@dataclass
class Task:
    """Processing task."""

    task_id: str
    pdf_name: str
    pdf_path: str = ""
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    created_at: str = ""
    error: str = ""
    result: Optional[Dict[str, Any]] = None
    expert_judgment: str = ""
    process_flow: Optional[ProcessFlow] = None
    process_flow_raw: str = ""
    llm_analysis: str = ""
    rag_results: Optional[Dict[str, Any]] = None

    # Batch processing fields
    files: Optional[List[Dict[str, Any]]] = None
    png_paths: Optional[List[str]] = None
    png_count: int = 0
    total_pages: int = 0
    file_count: int = 0
    comprehensive_judgment: str = ""
    individual_results: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "task_id": self.task_id,
            "pdf_name": self.pdf_name,
            "status": self.status.value
            if isinstance(self.status, TaskStatus)
            else self.status,
            "progress": self.progress,
            "created_at": self.created_at,
            "error": self.error,
        }


# Column definitions
COLUMNS = [
    "标签编码",
    "分厂",
    "专业类型",
    "工序内容",
    "工序描述",
    "工作中心",
    "操作时间",
    "准备时间",
    "工时基准件数",
    "工序状态",
]
