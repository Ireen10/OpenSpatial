from __future__ import annotations

import threading
import time
import unittest

from openspatial_metadata.cli_phase_timing import PhaseTimer, timed_phase


class TestCliPhaseTiming(unittest.TestCase):
    def test_timed_phase_accumulates(self) -> None:
        t = PhaseTimer()
        with timed_phase(t, "p1"):
            time.sleep(0.01)
        with timed_phase(t, "p1"):
            time.sleep(0.01)
        snap = t.snapshot()
        self.assertEqual(int(snap["p1"]["count"]), 2)
        self.assertGreater(snap["p1"]["total_s"], 0.0)

    def test_threaded_adds_merge(self) -> None:
        t = PhaseTimer()

        def worker() -> None:
            with timed_phase(t, "work"):
                time.sleep(0.01)

        th = [threading.Thread(target=worker) for _ in range(4)]
        for x in th:
            x.start()
        for x in th:
            x.join()
        snap = t.snapshot()
        self.assertEqual(int(snap["work"]["count"]), 4)
