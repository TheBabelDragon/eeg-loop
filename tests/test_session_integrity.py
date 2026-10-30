"""Session integrity foundation tests."""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from host.eegstream.session import (
    EEGPacket,
    PacketValidationError,
    SessionError,
    SessionFinalization,
    SessionHeader,
    SessionHeaderError,
    SessionIncompleteError,
    SessionIntegrityError,
    SessionReader,
    SessionWriter,
    VERSION_V1,
    VERSION_V2,
    compute_content_digest,
    write_synthetic,
)


def _minimal_header(**kwargs) -> SessionHeader:
    base = dict(
        session_id="test",
        sample_rate=100.0,
        channel_count=1,
        channel_names=["ch1"],
        source="test",
        created_at="2026-01-01T00:00:00Z",
    )
    base.update(kwargs)
    return SessionHeader(**base)


class RecordingSafetyTests(unittest.TestCase):
    def test_refuses_overwrite_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            write_synthetic(path, n_samples=10, overwrite=True)
            header = _minimal_header()
            with self.assertRaises(FileExistsError):
                SessionWriter(path, header)

    def test_overwrite_flag_allows_fixture_replace(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            write_synthetic(path, n_samples=10, overwrite=True)
            write_synthetic(path, n_samples=20, overwrite=True)
            self.assertEqual(SessionReader(path).sample_count(), 20)

    def test_failed_write_does_not_publish(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            header = _minimal_header()
            try:
                with SessionWriter(path, header) as w:
                    w.write_packet(EEGPacket(0, 0, 100.0, 1, [[1.0]]))
                    raise RuntimeError("simulated failure")
            except RuntimeError:
                pass
            self.assertFalse(path.exists())
            temps = list(Path(td).glob(".s.eeg.*.tmp"))
            self.assertEqual(temps, [])

    def test_atomic_publish_leaves_finalized(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            write_synthetic(path, n_samples=25, packet_size=5)
            self.assertTrue(path.exists())
            r = SessionReader(path)
            self.assertTrue(r.is_finalized())
            self.assertEqual(r.sample_count(), 25)

    def test_finalized_unchanged_after_failed_subsequent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            write_synthetic(path, n_samples=10, overwrite=True)
            before = path.read_bytes()
            header = _minimal_header(session_id="other")
            with self.assertRaises(FileExistsError):
                SessionWriter(path, header)
            self.assertEqual(path.read_bytes(), before)


class HeaderValidationTests(unittest.TestCase):
    def test_invalid_sample_rate(self):
        h = _minimal_header(sample_rate=0)
        with self.assertRaises(SessionHeaderError):
            h.validate()

    def test_nan_sample_rate(self):
        h = _minimal_header(sample_rate=float("nan"))
        with self.assertRaises(SessionHeaderError):
            h.validate()

    def test_inf_sample_rate(self):
        h = _minimal_header(sample_rate=float("inf"))
        with self.assertRaises(SessionHeaderError):
            h.validate()

    def test_invalid_channel_count(self):
        h = _minimal_header(channel_count=0)
        with self.assertRaises(SessionHeaderError):
            h.validate()

    def test_duplicate_channel_names(self):
        h = _minimal_header(channel_count=2, channel_names=["a", "a"])
        with self.assertRaises(SessionHeaderError):
            h.validate()

    def test_channel_name_count_mismatch(self):
        h = _minimal_header(channel_count=2, channel_names=["only"])
        with self.assertRaises(SessionHeaderError):
            h.validate()

    def test_empty_session_id(self):
        h = _minimal_header(session_id="")
        with self.assertRaises(SessionHeaderError):
            h.validate()

    def test_bad_format(self):
        h = _minimal_header(format="other")
        with self.assertRaises(SessionHeaderError):
            h.validate()

    def test_unsupported_version(self):
        h = _minimal_header(version=99)
        with self.assertRaises(SessionHeaderError):
            h.validate()


class PacketValidationTests(unittest.TestCase):
    def _writer_path(self, td):
        path = Path(td) / "p.eeg"
        header = _minimal_header()
        return path, header

    def test_negative_sequence(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                with self.assertRaises(PacketValidationError):
                    w.write_packet(EEGPacket(-1, 0, 100.0, 1, [[0.0]]))

    def test_negative_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                with self.assertRaises(PacketValidationError):
                    w.write_packet(EEGPacket(0, -1, 100.0, 1, [[0.0]]))

    def test_sequence_gap(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                w.write_packet(EEGPacket(0, 0, 100.0, 1, [[0.0]]))
                with self.assertRaises(PacketValidationError) as cm:
                    w.write_packet(EEGPacket(2, 10000, 100.0, 1, [[1.0]]))
                self.assertIn("gap", str(cm.exception).lower())

    def test_duplicate_sequence(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                w.write_packet(EEGPacket(0, 0, 100.0, 1, [[0.0]]))
                with self.assertRaises(PacketValidationError) as cm:
                    w.write_packet(EEGPacket(0, 10000, 100.0, 1, [[1.0]]))
                self.assertIn("duplicate", str(cm.exception).lower())

    def test_backward_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                w.write_packet(EEGPacket(0, 1000, 100.0, 1, [[0.0]]))
                with self.assertRaises(PacketValidationError) as cm:
                    w.write_packet(EEGPacket(1, 500, 100.0, 1, [[1.0]]))
                self.assertIn("backwards", str(cm.exception).lower())

    def test_repeated_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                w.write_packet(EEGPacket(0, 1000, 100.0, 1, [[0.0]]))
                with self.assertRaises(PacketValidationError) as cm:
                    w.write_packet(EEGPacket(1, 1000, 100.0, 1, [[1.0]]))
                self.assertIn("repeated", str(cm.exception).lower())

    def test_wrong_sample_rate(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                with self.assertRaises(PacketValidationError):
                    w.write_packet(EEGPacket(0, 0, 200.0, 1, [[0.0]]))

    def test_wrong_channel_count(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                with self.assertRaises(PacketValidationError):
                    w.write_packet(EEGPacket(0, 0, 100.0, 2, [[0.0, 1.0]]))

    def test_incorrect_row_width(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                with self.assertRaises(PacketValidationError):
                    w.write_packet(EEGPacket(0, 0, 100.0, 1, [[0.0, 1.0]]))

    def test_nan_sample(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                with self.assertRaises(PacketValidationError):
                    w.write_packet(EEGPacket(0, 0, 100.0, 1, [[float("nan")]]))

    def test_inf_sample(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                with self.assertRaises(PacketValidationError):
                    w.write_packet(EEGPacket(0, 0, 100.0, 1, [[float("inf")]]))

    def test_invalid_quality(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                with self.assertRaises(PacketValidationError):
                    w.write_packet(EEGPacket(0, 0, 100.0, 1, [[0.0]], quality=1.5))

    def test_empty_packet(self):
        with tempfile.TemporaryDirectory() as td:
            path, header = self._writer_path(td)
            with SessionWriter(path, header) as w:
                with self.assertRaises(PacketValidationError):
                    w.write_packet(EEGPacket(0, 0, 100.0, 1, []))


class ReaderIntegrityTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            write_synthetic(path, n_samples=50, packet_size=10, sample_rate=200.0)
            session = SessionReader(path)
            self.assertEqual(session.header.sample_rate, 200.0)
            self.assertEqual(session.sample_count(), 50)
            packets = list(session.packets())
            self.assertEqual([p.sequence for p in packets], list(range(len(packets))))
            self.assertTrue(session.is_finalized())

    def test_malformed_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.eeg"
            path.write_text(
                '{"format":"eeg-loop.session","version":1,"session_id":"x",'
                '"sample_rate":100,"channel_count":1,"channel_names":["ch1"],'
                '"units":"raw_counts","source":"t","created_at":"2026-01-01T00:00:00Z",'
                '"software_revision":"0.1"}\n'
                '{not json\n',
                encoding="utf-8",
            )
            with self.assertRaises(SessionError) as cm:
                SessionReader(path, require_finalization=False, verify_digest=False)
            self.assertIn("line", str(cm.exception).lower())

    def test_truncated_final_line(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trunc.eeg"
            write_synthetic(path, n_samples=10, overwrite=True)
            data = path.read_text(encoding="utf-8")
            path.write_text(data[:-2], encoding="utf-8")
            with self.assertRaises(SessionError):
                SessionReader(path, require_finalization=False)

    def test_missing_finalization_v2_strict(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nofin.eeg"
            lines = [
                json.dumps(
                    {
                        "format": "eeg-loop.session",
                        "version": 2,
                        "session_id": "test",
                        "sample_rate": 100.0,
                        "channel_count": 1,
                        "channel_names": ["ch1"],
                        "units": "raw_counts",
                        "source": "test",
                        "created_at": "2026-01-01T00:00:00Z",
                        "software_revision": "0.1.0-scaffold",
                    },
                    separators=(",", ":"),
                )
                + "\n",
                json.dumps(
                    {
                        "sequence": 0,
                        "timestamp_us": 0,
                        "sample_rate": 100.0,
                        "channel_count": 1,
                        "samples": [[1.0]],
                        "status": 0,
                        "quality": 1.0,
                    },
                    separators=(",", ":"),
                )
                + "\n",
            ]
            path.write_text("".join(lines), encoding="utf-8")
            with self.assertRaises(SessionIncompleteError):
                SessionReader(path, strict=True)

    def test_v1_without_finalization_readable(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "v1.eeg"
            header = _minimal_header(version=VERSION_V1)
            with SessionWriter(path, header, version=VERSION_V1) as w:
                w.write_packet(EEGPacket(0, 0, 100.0, 1, [[1.0]]))
            r = SessionReader(path, require_finalization=False)
            self.assertEqual(r.header.version, VERSION_V1)
            self.assertFalse(r.is_finalized())
            self.assertEqual(r.sample_count(), 1)

    def test_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            write_synthetic(path, n_samples=10, overwrite=True)
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines(keepends=True)
            lines[1] = lines[1].replace("10.0", "11.0", 1)
            path.write_text("".join(lines), encoding="utf-8")
            with self.assertRaises(SessionIntegrityError):
                SessionReader(path)

    def test_digest_verifies(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            write_synthetic(path, n_samples=10, overwrite=True)
            r = SessionReader(path)
            self.assertTrue(r.is_finalized())
            report = r.integrity_report()
            self.assertTrue(report["digest_ok"])
            self.assertEqual(report["digest_sha256"], r.finalization.sha256)

    def test_streaming_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            write_synthetic(path, n_samples=100, packet_size=10)
            a = [p.sequence for p in SessionReader(path).packets()]
            b = [p.sequence for p in SessionReader(path).packets()]
            self.assertEqual(a, b)

    def test_diagnose_structure(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            write_synthetic(path, n_samples=30, packet_size=10)
            diag = SessionReader(path).diagnose()
            self.assertTrue(diag.ok)
            self.assertEqual(diag.sample_count, 30)
            self.assertEqual(diag.packet_count, 3)


class RegressionTests(unittest.TestCase):
    def test_legacy_roundtrip_api(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "t.eeg"
            write_synthetic(path, n_samples=50, packet_size=10, sample_rate=200.0)
            session = SessionReader(path)
            self.assertEqual(session.header.sample_rate, 200.0)
            self.assertEqual(session.header.channel_count, 2)
            packets = list(session.packets())
            self.assertEqual([p.sequence for p in packets], list(range(len(packets))))
            self.assertEqual(session.sample_count(), 50)

    def test_rejects_sequence_gap_writer(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.eeg"
            header = _minimal_header()
            with SessionWriter(path, header) as w:
                w.write_packet(EEGPacket(0, 0, 100.0, 1, [[0.0]]))
                with self.assertRaises(PacketValidationError):
                    w.write_packet(EEGPacket(2, 10000, 100.0, 1, [[1.0]]))


if __name__ == "__main__":
    unittest.main()
