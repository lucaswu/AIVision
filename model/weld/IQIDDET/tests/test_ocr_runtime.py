import sys
import textwrap
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gauge.runtime.ocr_runtime import PaddleOCRSubprocessClient  # noqa: E402

# Fake worker speaking the same line protocol: ready line, then one reply per request.
_WORKER = textwrap.dedent(
    """
    import json, sys, time
    print(json.dumps({"ok": True}), flush=True)
    for line in sys.stdin:
        op = json.loads(line).get("op")
        if op == "close":
            break
        if op == "detect":
            print(json.dumps({"ok": True, "result": {"boxes": [1, 2]}}), flush=True)
        elif op == "recognize":
            time.sleep(5)
        elif op == "crash":
            sys.exit(3)
    """
)


class PaddleOCRSubprocessClientTest(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.script = Path(self._tmp.name) / "fake_worker.py"
        self.script.write_text(_WORKER, encoding="utf-8")
        self.image = np.zeros((4, 4, 3), dtype=np.uint8)

    def _client(self, **kw):
        return PaddleOCRSubprocessClient(worker_script=str(self.script), **kw)

    def test_request_response_roundtrip(self):
        with self._client(request_timeout_s=10) as client:
            self.assertEqual(client.detect(self.image), {"boxes": [1, 2]})
            self.assertEqual(client.detect(self.image), {"boxes": [1, 2]})

    def test_request_timeout_closes_worker(self):
        client = self._client(request_timeout_s=0.5)
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            client.recognize(self.image)
        self.assertIsNone(client.process)

    def test_worker_exit_is_reported(self):
        client = self._client(request_timeout_s=5)
        try:
            client.process.stdin.write('{"op": "crash"}\n')
            client.process.stdin.flush()
            with self.assertRaisesRegex(RuntimeError, "exited unexpectedly"):
                client._read_response()
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
