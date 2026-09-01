import tempfile
import unittest
from pathlib import Path

from host.eegstream.session import (
    EEGPacket,
    SessionHeader,
    SessionReader,
    SessionWriter,
    write_synthetic,
)


class SessionProtocolTests(unittest.TestCase):
    def test_roundtrip_and_sequence(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "t.eeg"
            write_synthetic(path, n_samples=50, packet_size=10, sample_rate=200.0)
            session = SessionReader(path)
            self.assertEqual(session.header.sample_rate, 200.0)
            self.assertEqual(session.header.channel_count, 2)
            packets = list(session.packets())
            self.assertEqual([p.sequence for p in packets], list(range(len(packets))))
            self.assertEqual(session.sample_count(), 50)

    def test_rejects_sequence_gap(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.eeg"
            header = SessionHeader(
                session_id="bad",
                sample_rate=100.0,
                channel_count=1,
                channel_names=["ch1"],
                source="test",
            )
            with SessionWriter(path, header) as w:
                w.write_packet(EEGPacket(0, 0, 100.0, 1, [[0.0]]))
                with self.assertRaises(ValueError):
                    w.write_packet(EEGPacket(2, 10000, 100.0, 1, [[1.0]]))


if __name__ == "__main__":
    unittest.main()
