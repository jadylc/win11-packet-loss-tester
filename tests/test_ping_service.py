from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from packet_loss_tester.ping_service import parse_ping_output
from packet_loss_tester.probe_models import ProbeStats


class PingServiceTests(unittest.TestCase):
    def test_parse_english_success_output(self) -> None:
        output = """
Pinging 8.8.8.8 with 32 bytes of data:
Reply from 8.8.8.8: bytes=32 time=18ms TTL=117
        """.strip()
        result = parse_ping_output(output, returncode=0, sequence=1, target="8.8.8.8")
        self.assertTrue(result.success)
        self.assertEqual(result.status, "成功")
        self.assertEqual(result.latency_ms, 18.0)
        self.assertEqual(result.transport, "ICMP")

    def test_parse_chinese_timeout_output(self) -> None:
        output = """
正在 Ping 1.1.1.1 具有 32 字节的数据:
请求超时。
        """.strip()
        result = parse_ping_output(output, returncode=1, sequence=2, target="1.1.1.1")
        self.assertFalse(result.success)
        self.assertEqual(result.status, "请求超时")
        self.assertIsNone(result.latency_ms)
        self.assertEqual(result.transport, "ICMP")

    def test_probe_stats_calculation(self) -> None:
        first = parse_ping_output("Reply from 8.8.8.8: bytes=32 time=20ms TTL=118", 0, 1, "8.8.8.8")
        second = parse_ping_output("Reply from 8.8.8.8: bytes=32 time=32ms TTL=118", 0, 2, "8.8.8.8")
        missed = parse_ping_output("Request timed out.", 1, 3, "8.8.8.8")
        stats = ProbeStats.from_results([first, second, missed])
        self.assertEqual(stats.sent, 3)
        self.assertEqual(stats.received, 2)
        self.assertEqual(stats.lost, 1)
        self.assertAlmostEqual(stats.loss_rate, 33.3333333333, places=2)
        self.assertAlmostEqual(stats.avg_latency_ms or 0, 26.0)
        self.assertAlmostEqual(stats.jitter_ms or 0, 12.0)


if __name__ == "__main__":
    unittest.main()
