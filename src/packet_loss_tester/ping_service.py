from __future__ import annotations

import locale
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime

from .probe_models import ProbeResult

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_LATENCY_PATTERN = re.compile(r"(?:time|时间)\s*[=<]\s*(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)
_STATUS_PATTERNS = [
    (re.compile(r"request timed out|请求超时", re.IGNORECASE), "请求超时"),
    (
        re.compile(
            r"destination (?:host|net) unreachable|目标主机不可达|无法访问目标主机|目标网络不可达",
            re.IGNORECASE,
        ),
        "目标不可达",
    ),
    (
        re.compile(
            r"could not find host|找不到主机|unknown host|name or service not known|temporary failure in name resolution",
            re.IGNORECASE,
        ),
        "无法解析主机",
    ),
    (re.compile(r"general failure|一般故障", re.IGNORECASE), "网络故障"),
]


@dataclass(slots=True)
class PingRequest:
    target: str
    count: int | None
    interval_seconds: float
    timeout_ms: int
    payload_size: int


def ensure_ping_available() -> None:
    if shutil.which("ping"):
        return
    raise FileNotFoundError("系统中未找到 ping 命令。")


def build_ping_command(target: str, timeout_ms: int, payload_size: int) -> list[str]:
    system_name = platform.system().lower()
    if "windows" in system_name:
        return ["ping", "-n", "1", "-w", str(timeout_ms), "-l", str(payload_size), target]
    timeout_seconds = max(1, round(timeout_ms / 1000))
    return ["ping", "-c", "1", "-W", str(timeout_seconds), "-s", str(payload_size), target]


def parse_ping_output(output: str, returncode: int, sequence: int, target: str) -> ProbeResult:
    latency_match = _LATENCY_PATTERN.search(output)
    latency_ms = float(latency_match.group(1)) if latency_match else None
    success = latency_ms is not None

    if success:
        status = "成功"
    else:
        status = "丢包"
        for pattern, label in _STATUS_PATTERNS:
            if pattern.search(output):
                status = label
                break
        if returncode == 0 and "ttl" in output.lower():
            status = "成功"
            success = True

    return ProbeResult(
        sequence=sequence,
        sampled_at=datetime.now(),
        target=target,
        success=success,
        latency_ms=latency_ms,
        status=status,
        raw_output=output.strip(),
        transport="ICMP",
    )


def run_single_ping(request: PingRequest, sequence: int) -> ProbeResult:
    ensure_ping_available()
    command = build_ping_command(
        target=request.target,
        timeout_ms=request.timeout_ms,
        payload_size=request.payload_size,
    )
    encoding = locale.getpreferredencoding(False) or "utf-8"
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding=encoding,
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            timeout=max(5, request.timeout_ms / 1000 + 3),
            check=False,
        )
        output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
        return parse_ping_output(output, completed.returncode, sequence, request.target)
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return ProbeResult(
            sequence=sequence,
            sampled_at=datetime.now(),
            target=request.target,
            success=False,
            latency_ms=None,
            status="执行超时",
            raw_output=output.strip() or "ping 命令执行超时。",
            transport="ICMP",
        )
