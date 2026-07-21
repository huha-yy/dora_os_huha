import numpy as np
import pytest

from body_tracking.health.backends import make_backend, POSBackend, CHROMBackend
from body_tracking.health.signal_utils import resample_uniform, hr_from_signal


def _pulsatile_rgb(fps=30.0, secs=15.0, hr_hz=1.2):
    t = np.arange(0, secs, 1 / fps)
    pulse = 0.02 * np.sin(2 * np.pi * hr_hz * t)
    # Skin-like base with the pulse modulating green strongest.
    r = 0.6 + 0.3 * pulse + 0.001 * np.random.RandomState(0).randn(t.size)
    g = 0.5 + 1.0 * pulse + 0.001 * np.random.RandomState(1).randn(t.size)
    b = 0.4 + 0.2 * pulse + 0.001 * np.random.RandomState(2).randn(t.size)
    return t, np.stack([r, g, b], axis=1)


def _pulsatile_rgb_with_common_mode_artifact(
    fps=30.0,
    secs=15.0,
    hr_hz=1.2,
    artifact_hz=2.5,
    artifact_amp=0.12,
    pulse_amp=0.03,
    skin_vec=(0.4, 0.9, 0.4),
    base=(0.3, 0.5, 0.4),
    noise=0.0005,
):
    """Synthetic RGB traces containing a TRUE pulse at ``hr_hz`` with
    per-channel amplitudes proportional to a skin-tone vector (strongest in
    green, as in real skin), PLUS a much larger common-mode intensity
    artifact at a different, in-band frequency (``artifact_hz``) applied
    multiplicatively and identically to all three channels -- modeling
    illumination flicker or motion-induced brightness change.

    POS and CHROM both project the temporally-normalized channels onto
    directions whose coefficients sum to zero (POS: G-B and G+B-2R; CHROM:
    3R-2G and 1.5R+G-1.5B, whose difference also sums to zero), so a
    component common to all channels cancels exactly regardless of *which*
    channel is assigned to which row. A naive single channel extractor has
    no such immunity and should instead lock onto the artifact.

    ``skin_vec`` deliberately sets the R and B gains equal (0.4, 0.4) with a
    much stronger G gain (0.9). This does not change whether the common-mode
    artifact is rejected (any zero-sum row assignment rejects it exactly,
    independent of skin_vec/base), but it does make an *incorrect* row
    assignment (e.g. using R where G belongs) measurably starve the
    projection of true pulse signal -- with R gain == B gain, an R-B row
    carries zero net pulse content, so a POS variant that swaps R for G
    must rely entirely on the weaker remaining row and recovers the pulse
    with markedly degraded SNR/confidence rather than the clean, dominant
    peak the correct G-based rows produce.
    """
    t = np.arange(0, secs, 1 / fps)
    pulse = np.sin(2 * np.pi * hr_hz * t)
    artifact = artifact_amp * np.sin(2 * np.pi * artifact_hz * t)
    channels = []
    for i, (base_c, skin_c) in enumerate(zip(base, skin_vec)):
        gain = pulse_amp * skin_c
        c = base_c * (1 + artifact) * (1 + gain * pulse)
        c = c + noise * np.random.RandomState(10 + i).randn(t.size)
        channels.append(c)
    return t, np.stack(channels, axis=1)


@pytest.mark.parametrize("backend_cls", [POSBackend, CHROMBackend])
def test_backend_recovers_heart_rate(backend_cls):
    t, rgb = _pulsatile_rgb()
    est = backend_cls().estimate(rgb, t)
    assert est.hr_bpm is not None
    assert abs(est.hr_bpm - 72.0) < 5.0
    assert 0.0 <= est.confidence <= 1.0


@pytest.mark.parametrize("backend_cls", [POSBackend, CHROMBackend])
def test_backend_rejects_common_mode_artifact(backend_cls):
    """POS/CHROM exist specifically to reject common-mode intensity
    artifacts (illumination flicker, motion) that are much larger than the
    true pulsatile signal. This is the property the previous fixture
    (identical in-phase sinusoid on every channel, differing only by a
    fixed gain) could not exercise, since any linear combination of that
    fixture recovers the same frequency regardless of correctness.

    Both the heart-rate value AND a high confidence floor are asserted.
    Rejecting a *common-mode* artifact (same waveform on every channel) is
    guaranteed by the coefficients of ANY zero-sum row pair -- including a
    wrong one, e.g. using R where the correct formula uses G -- because the
    common term cancels identically regardless of channel labels. So a
    channel-swap bug cannot be caught by frequency alone: with a single
    in-phase pulse waveform (differing only by per-channel amplitude), a
    wrong row assignment still contains *some* nonzero true-pulse
    component and still locks onto ~72 bpm. What a wrong assignment loses
    is signal quality: it discards the strongest (green-weighted) row and
    is left recovering the pulse from a much weaker, noisier combination.
    The confidence floor below is what actually catches that regression;
    see the swapped-rows negative control in the Task 4 fix report.
    """
    t, rgb = _pulsatile_rgb_with_common_mode_artifact()
    est = backend_cls().estimate(rgb, t)
    assert est.hr_bpm is not None
    assert abs(est.hr_bpm - 72.0) < 5.0
    assert est.confidence > 0.95


def test_naive_green_channel_locks_onto_artifact_not_pulse():
    """Proves the fixture above is genuinely discriminative: a naive
    extractor using only the (temporally-normalized) green channel has no
    common-mode rejection, so it should lock onto the artifact frequency
    (~150 bpm) instead of the true pulse (~72 bpm). If this failed, the
    fixture would not actually require common-mode rejection and
    `test_backend_rejects_common_mode_artifact` above would be unable to
    catch a degenerate/broken backend.
    """
    t, rgb = _pulsatile_rgb_with_common_mode_artifact()
    mean = rgb.mean(axis=0)
    green_normed = rgb[:, 1] / mean[1]
    fps = (t.size - 1) / (t[-1] - t[0])
    uniform = resample_uniform(t, green_normed, fps)
    hr, _snr, _dominance = hr_from_signal(uniform, fps)
    assert hr is not None
    assert abs(hr - 72.0) > 5.0
    assert abs(hr - 150.0) < 5.0


def test_make_backend_selects_and_rejects():
    assert isinstance(make_backend("pos"), POSBackend)
    assert isinstance(make_backend("chrom"), CHROMBackend)
    with pytest.raises(ValueError):
        make_backend("deep")
