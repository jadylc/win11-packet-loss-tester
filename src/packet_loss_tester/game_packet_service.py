from __future__ import annotations

import socket
import struct
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .probe_models import ProbeResult

_PACKET_MAGIC = b"PLT2"
_PACKET_HEADER = struct.Struct("!4sIQ")
_SERVER_POLL_SECONDS = 0.25


@dataclass(slots=True)
class GamePacketRequest:
    target: str
    port: int
    count: int | None
    interval_seconds: float
    timeout_ms: int
    payload_size: int
    burst_size: int


def build_game_packet(sequence: int, sent_ns: int, payload_size: int) -> bytes:
    filler_size = max(0, payload_size)
    filler = bytes([sequence % 251]) * filler_size
    return _PACKET_HEADER.pack(_PACKET_MAGIC, sequence, sent_ns) + filler


def parse_game_packet(packet: bytes) -> tuple[int, int, int]:
    if len(packet) < _PACKET_HEADER.size:
        raise ValueError("数据包长度不足。")
    magic, sequence, sent_ns = _PACKET_HEADER.unpack_from(packet)
    if magic != _PACKET_MAGIC:
        raise ValueError("不是本工具的数据包。")
    return sequence, sent_ns, len(packet) - _PACKET_HEADER.size


class UdpEchoServer:
    def __init__(
        self,
        listen_host: str,
        port: int,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.listen_host = listen_host
        self.port = port
        self.log_callback = log_callback
        self.bound_host = listen_host
        self.bound_port = port
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> int:
        if self.is_running:
            return self.bound_port

        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.bind((self.listen_host, self.port))
        udp_socket.settimeout(_SERVER_POLL_SECONDS)
        self.bound_host, self.bound_port = udp_socket.getsockname()[:2]
        self._socket = udp_socket
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._thread.start()
        self._log(f"UDP 回显服务已监听 {self.bound_host}:{self.bound_port}")
        return self.bound_port

    def stop(self) -> None:
        if not self.is_running and self._socket is None:
            return

        self._stop_event.set()
        udp_socket = self._socket
        self._socket = None
        if udp_socket is not None:
            udp_socket.close()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._thread = None
        self._log("UDP 回显服务已停止")

    def _serve_loop(self) -> None:
        while not self._stop_event.is_set():
            udp_socket = self._socket
            if udp_socket is None:
                return
            try:
                packet, client = udp_socket.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                if self._stop_event.is_set():
                    return
                self._log("UDP 回显服务异常中断。")
                return

            try:
                parse_game_packet(packet)
            except ValueError:
                continue

            try:
                udp_socket.sendto(packet, client)
            except OSError:
                if self._stop_event.is_set():
                    return
                self._log("UDP 回包失败。")
                return

    def _log(self, message: str) -> None:
        if self.log_callback is not None:
            self.log_callback(message)


class GamePacketProbeSession:
    def __init__(self, request: GamePacketRequest) -> None:
        self.request = request
        self._socket: socket.socket | None = None

    def __enter__(self) -> "GamePacketProbeSession":
        self.open()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.close()

    def open(self) -> None:
        if self._socket is not None:
            return
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.connect((self.request.target, self.request.port))
        self._socket = udp_socket

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def probe_once(self, sequence: int, stop_event: threading.Event | None = None) -> ProbeResult:
        if self._socket is None:
            self.open()

        assert self._socket is not None
        target = f"{self.request.target}:{self.request.port}"
        sent_ns = time.perf_counter_ns()
        packet = build_game_packet(sequence, sent_ns, self.request.payload_size)

        try:
            self._socket.send(packet)
        except OSError as exc:
            return ProbeResult(
                sequence=sequence,
                sampled_at=datetime.now(),
                target=target,
                success=False,
                latency_ms=None,
                status="发送失败",
                raw_output=f"UDP 发送失败: {exc}",
                transport="UDP",
            )

        deadline = time.monotonic() + self.request.timeout_ms / 1000
        while True:
            if stop_event is not None and stop_event.is_set():
                return ProbeResult(
                    sequence=sequence,
                    sampled_at=datetime.now(),
                    target=target,
                    success=False,
                    latency_ms=None,
                    status="已停止",
                    raw_output="测试被用户停止。",
                    transport="UDP",
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            self._socket.settimeout(min(remaining, _SERVER_POLL_SECONDS))
            try:
                echoed = self._socket.recv(65535)
            except socket.timeout:
                continue
            except ConnectionResetError as exc:
                return ProbeResult(
                    sequence=sequence,
                    sampled_at=datetime.now(),
                    target=target,
                    success=False,
                    latency_ms=None,
                    status="端口不可达",
                    raw_output=f"UDP 回包失败: {exc}",
                    transport="UDP",
                )
            except OSError as exc:
                return ProbeResult(
                    sequence=sequence,
                    sampled_at=datetime.now(),
                    target=target,
                    success=False,
                    latency_ms=None,
                    status="连接异常",
                    raw_output=f"UDP 收包失败: {exc}",
                    transport="UDP",
                )

            try:
                echoed_sequence, echoed_sent_ns, echoed_payload_size = parse_game_packet(echoed)
            except ValueError:
                continue

            if echoed_sequence != sequence or echoed_sent_ns != sent_ns:
                continue

            latency_ms = (time.perf_counter_ns() - sent_ns) / 1_000_000
            return ProbeResult(
                sequence=sequence,
                sampled_at=datetime.now(),
                target=target,
                success=True,
                latency_ms=latency_ms,
                status="成功",
                raw_output=(
                    f"udp seq={sequence} bytes={len(packet)} reply_bytes={len(echoed)} "
                    f"payload={echoed_payload_size} rtt={latency_ms:.2f}ms"
                ),
                transport="UDP",
            )

        return ProbeResult(
            sequence=sequence,
            sampled_at=datetime.now(),
            target=target,
            success=False,
            latency_ms=None,
            status="回包超时",
            raw_output=(
                f"udp seq={sequence} bytes={len(packet)} timeout={self.request.timeout_ms}ms "
                "未收到匹配回包。"
            ),
            transport="UDP",
        )
