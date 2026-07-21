"""The gate that decides whether we show a number at all.

Everything else in this package is tested against a pulse we injected. Nothing was
testing the opposite and far more dangerous case: feed the estimator NO pulse and see
whether it invents one.

It does. With `min_confidence = 0.5`, pure Gaussian noise cleared the gate and
published a heart rate in ~1 window in 6. Noise confidence is not near zero -- the
formula `0.5*snr/(snr+4) + 0.5*dominance` has a floor around 0.44 and a p95 of 0.57,
because a random spectrum still has *some* peak somewhere in the 0.7-4 Hz band and
dominance rewards it. The gate was sitting inside the noise distribution.

This matters in the field, not just in theory. The other gates (face present, size,
FPS, motion, illumination) all pass happily for a real, still, well-lit face whose
rPPG signal is simply too weak to recover -- poor lighting, an unlucky skin tone, a
camera with aggressive denoising. That window IS noise, and it was 1-in-6 to produce
a confident phantom heart rate. AGENTS.md section 5: prefer a loud failure over a
plausible-but-wrong number.

These tests are statistical on purpose. A single-window assertion would be flaky in
exactly the direction that hides the bug.
"""

import numpy as np
import pytest

from body_tracking.health.backends import CHROMBackend, POSBackend
from body_tracking.health.config import Gates

FPS = 30.0
N = 300              # a 10s window -- the ambient default
TS = np.arange(N) / FPS
TRIALS = 200

GATE = Gates().min_confidence

# A real rPPG signal is a ~0.5-2% modulation of the green channel under decent
# lighting. 1% is an ordinary, not a generous, case.
REALISTIC_PULSE_AMP = 0.01
HR_HZ = 1.2          # 72 bpm


def _noise_window(rng):
    return 128.0 + rng.normal(0, 2.0, (N, 3))


def _pulse_window(rng, amp=REALISTIC_PULSE_AMP):
    p = amp * np.sin(2 * np.pi * HR_HZ * TS)
    rgb = np.empty((N, 3))
    rgb[:, 0] = 128.0 * (1 + 0.3 * p)   # R responds weakly
    rgb[:, 1] = 128.0 * (1 + 1.0 * p)   # G carries the pulse
    rgb[:, 2] = 128.0 * (1 + 0.2 * p)   # B weakly
    return rgb + rng.normal(0, 0.5, (N, 3))


@pytest.mark.parametrize("backend", [POSBackend, CHROMBackend])
def test_pure_noise_almost_never_publishes_a_heart_rate(backend):
    """THE regression test. At min_confidence=0.5 this was ~17% and shipped."""
    b = backend()

    published = sum(
        b.estimate(_noise_window(np.random.default_rng(s)), TS).confidence >= GATE
        for s in range(TRIALS)
    )
    rate = published / TRIALS

    assert rate <= 0.02, (
        f"{backend.__name__} published a heart rate from PURE NOISE in "
        f"{rate:.1%} of windows (gate={GATE}). The gate is inside the noise "
        f"distribution -- a face too poorly lit to read will show a phantom pulse."
    )


@pytest.mark.parametrize("backend", [POSBackend, CHROMBackend])
def test_a_realistic_pulse_still_gets_through(backend):
    """The other half of the trade. A gate that rejects noise by rejecting
    everything is not a fix -- it is a feature that never works."""
    b = backend()

    accepted = 0
    for s in range(TRIALS):
        est = b.estimate(_pulse_window(np.random.default_rng(s)), TS)
        if est.confidence >= GATE and est.hr_bpm is not None and abs(est.hr_bpm - 72.0) < 6.0:
            accepted += 1
    rate = accepted / TRIALS

    assert rate >= 0.95, (
        f"{backend.__name__} accepted a correct HR from an ordinary 1% pulse in only "
        f"{rate:.1%} of windows (gate={GATE}). The gate is too strict to be usable."
    )


@pytest.mark.parametrize("backend", [POSBackend, CHROMBackend])
def test_the_gate_sits_between_the_noise_and_signal_distributions(backend):
    """A gate is only sitable if the two distributions separate. Pins that separation
    so a change to the confidence formula cannot quietly erase it, and pins the gate
    inside the gap rather than inside either distribution -- which is where 0.5 was.

    Percentiles, not max/min: the tails of 200 random draws move around, and a
    max-vs-min assertion would be flaky in the direction that hides the bug."""
    b = backend()

    noise = np.array([b.estimate(_noise_window(np.random.default_rng(s)), TS).confidence
                      for s in range(TRIALS)])
    pulse = np.array([b.estimate(_pulse_window(np.random.default_rng(s)), TS).confidence
                      for s in range(TRIALS)])

    noise_ceiling = float(np.percentile(noise, 99))
    signal_floor = float(np.percentile(pulse, 1))

    assert noise_ceiling < signal_floor, (
        f"{backend.__name__}: noise reaches {noise_ceiling:.3f} (p99) while a real pulse "
        f"can score {signal_floor:.3f} (p01) -- the distributions overlap and NO gate "
        f"value can separate them. The confidence formula itself needs work."
    )
    assert noise_ceiling < GATE < signal_floor, (
        f"{backend.__name__}: gate {GATE} is not inside the gap "
        f"[{noise_ceiling:.3f}, {signal_floor:.3f}]."
    )
