from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from machine_transport import GpioConfig, GpioPlcTransport, MachineCommunicationError


class FakeOutput:
    def __init__(self):
        self.events = []

    def on(self):
        self.events.append("on")

    def off(self):
        self.events.append("off")

    def close(self):
        self.events.append("close")


class FakeInput:
    def __init__(self, *, active=False, activates=True, deactivates=True):
        self.is_active = active
        self.activates = activates
        self.deactivates = deactivates

    def wait_for_active(self, timeout):
        return self.activates

    def wait_for_inactive(self, timeout):
        return self.deactivates

    def close(self):
        pass


class GpioPlcTransportTests(unittest.TestCase):
    def make_transport(self, input_device=None):
        output = FakeOutput()
        transport = GpioPlcTransport(
            GpioConfig(pulse_seconds=0.01, gap_seconds=0.02),
            output_device=output,
            input_device=input_device or FakeInput(),
            sleep=lambda _seconds: None,
        )
        return transport, output

    def test_position_is_encoded_as_pulse_count(self):
        transport, output = self.make_transport()
        transport.send(3)
        self.assertEqual(output.events, ["on", "off"] * 3)

    def test_stale_completion_must_return_inactive(self):
        transport, output = self.make_transport(
            FakeInput(active=True, deactivates=False)
        )
        with self.assertRaises(MachineCommunicationError):
            transport.send(2)
        self.assertEqual(output.events, [])

    def test_completion_timeout_is_an_error(self):
        transport, _output = self.make_transport(FakeInput(activates=False))
        with self.assertRaises(MachineCommunicationError):
            transport.send(1)


if __name__ == "__main__":
    unittest.main()
