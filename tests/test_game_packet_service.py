from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from packet_loss_tester.game_packet_service import (
    GamePacketProbeSession,
    GamePacketRequest,
    UdpEchoServer,
    build_game_packet,
    parse_game_packet,
)


class GamePacketServiceTests(unittest.TestCase):
    def test_build_and_parse_game_packet(self) -> None:
        packet = build_game_packet(sequence=7, sent_ns=123456789, payload_size=48)
        sequence, sent_ns, payload_size = parse_game_packet(packet)
        self.assertEqual(sequence, 7)
        self.assertEqual(sent_ns, 123456789)
        self.assertEqual(payload_size, 48)

    def test_udp_echo_probe_round_trip(self) -> None:
        server = UdpEchoServer("127.0.0.1", 0)
        try:
            port = server.start()
            request = GamePacketRequest(
                target="127.0.0.1",
                port=port,
                count=1,
                interval_seconds=0.02,
                timeout_ms=500,
                payload_size=32,
                burst_size=1,
            )
            with GamePacketProbeSession(request) as session:
                result = session.probe_once(1)
        finally:
            server.stop()

        self.assertTrue(result.success, result.raw_output)
        self.assertEqual(result.status, "成功")
        self.assertEqual(result.transport, "UDP")
        self.assertIsNotNone(result.latency_ms)
        self.assertGreaterEqual(result.latency_ms or 0, 0.0)


if __name__ == "__main__":
    unittest.main()
