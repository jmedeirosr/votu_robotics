"""Communication backends for the PLC-controlled machine.

The GPIO backend replaces the PIC: a numeric position is emitted as a pulse
train and the call returns only after the PLC completion input becomes active.
BCM pin numbering is used throughout.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable


class MachineCommunicationError(RuntimeError):
    """Raised when a command cannot be delivered or acknowledged."""


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class GpioConfig:
    pulse_pin: int = 17
    finished_pin: int = 27
    pulse_seconds: float = 0.05
    gap_seconds: float = 0.05
    finished_timeout_seconds: float = 120.0
    output_active_high: bool = True
    finished_active_high: bool = True
    finished_pull_up: bool = False

    @classmethod
    def from_environment(cls) -> "GpioConfig":
        return cls(
            pulse_pin=int(os.getenv("VOTU_PULSE_PIN", "17")),
            finished_pin=int(os.getenv("VOTU_FINISHED_PIN", "27")),
            pulse_seconds=float(os.getenv("VOTU_PULSE_SECONDS", "0.05")),
            gap_seconds=float(os.getenv("VOTU_PULSE_GAP_SECONDS", "0.05")),
            finished_timeout_seconds=float(os.getenv("VOTU_FINISHED_TIMEOUT", "120")),
            output_active_high=_env_bool("VOTU_OUTPUT_ACTIVE_HIGH", True),
            finished_active_high=_env_bool("VOTU_FINISHED_ACTIVE_HIGH", True),
            finished_pull_up=_env_bool("VOTU_FINISHED_PULL_UP", False),
        )


class GpioPlcTransport:
    def __init__(
        self,
        config: GpioConfig | None = None,
        *,
        output_device=None,
        input_device=None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.config = config or GpioConfig.from_environment()
        self._sleep = sleep

        if output_device is None or input_device is None:
            try:
                from gpiozero import DigitalInputDevice, DigitalOutputDevice
            except ImportError as exc:
                raise MachineCommunicationError(
                    "Backend GPIO selecionado, mas gpiozero não está instalado."
                ) from exc

            output_device = output_device or DigitalOutputDevice(
                self.config.pulse_pin,
                active_high=self.config.output_active_high,
                initial_value=False,
            )
            input_options = {
                "pull_up": True if self.config.finished_pull_up else None,
                "bounce_time": 0.02,
            }
            if not self.config.finished_pull_up:
                input_options["active_state"] = self.config.finished_active_high
            input_device = input_device or DigitalInputDevice(
                self.config.finished_pin,
                **input_options,
            )

        self.output = output_device
        self.finished = input_device

    def send(self, value: int) -> None:
        pulse_count = int(str(value).replace("➤", "").strip())
        if pulse_count <= 0:
            raise ValueError("A posição deve ser um número inteiro maior que zero.")

        # Acknowledge must return to idle before a new command. This prevents a
        # stale high signal from completing the next pot immediately.
        if self.finished.is_active:
            if not self.finished.wait_for_inactive(
                timeout=self.config.finished_timeout_seconds
            ):
                raise MachineCommunicationError(
                    "O sinal de finalização do CLP permaneceu ativo."
                )

        for index in range(pulse_count):
            self.output.on()
            self._sleep(self.config.pulse_seconds)
            self.output.off()
            if index + 1 < pulse_count:
                self._sleep(self.config.gap_seconds)

        if not self.finished.wait_for_active(
            timeout=self.config.finished_timeout_seconds
        ):
            raise MachineCommunicationError(
                "Timeout aguardando a finalização do CLP."
            )

    def close(self) -> None:
        self.output.off()
        self.output.close()
        self.finished.close()
