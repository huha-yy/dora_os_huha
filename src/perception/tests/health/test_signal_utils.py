import numpy as np

from body_tracking.health.signal_utils import resample_uniform, bandpass, hr_from_signal


def test_resample_uniform_preserves_endpoints():
    ts = np.array([0.0, 0.1, 0.35, 0.4])
    vals = np.array([0.0, 1.0, 2.0, 3.0])
    out = resample_uniform(ts, vals, fps=20.0)
    assert out.shape[0] == int(round((0.4 - 0.0) * 20.0)) + 1
    assert np.isclose(out[0], 0.0) and np.isclose(out[-1], 3.0)


def test_bandpass_removes_dc_offset():
    fps = 30.0
    t = np.arange(0, 10, 1 / fps)
    sig = 100.0 + np.sin(2 * np.pi * 1.2 * t)  # 72 bpm on a big DC offset
    out = bandpass(sig, fps)
    assert abs(out.mean()) < 1e-6
    assert out.std() > 0.1


def test_bandpass_attenuates_out_of_band_power():
    # Proves the Butterworth filter actually band-limits the signal, rather
    # than just relying on `filtered - filtered.mean()` for the DC-removal
    # assertions above (which pass trivially even with no filtering at all).
    fps = 30.0
    t = np.arange(0, 20, 1 / fps)  # 600 samples, generous frequency resolution
    in_band_freq = 1.2  # 72 bpm, inside the default 0.7-4.0 Hz pass band
    out_band_high_freq = 10.0  # well above hi_hz=4.0
    out_band_low_freq = 0.1  # well below lo_hz=0.7 (slow drift)
    sig = (
        100.0
        + np.sin(2 * np.pi * in_band_freq * t)
        + np.sin(2 * np.pi * out_band_high_freq * t)
        + np.sin(2 * np.pi * out_band_low_freq * t)
    )

    out = bandpass(sig, fps)

    freqs = np.fft.rfftfreq(out.size, d=1.0 / fps)
    spectrum = np.abs(np.fft.rfft(out)) ** 2
    in_band_mask = np.abs(freqs - in_band_freq) <= 0.3
    out_band_mask = (np.abs(freqs - out_band_high_freq) <= 0.5) | (
        np.abs(freqs - out_band_low_freq) <= 0.3
    )

    in_band_power = float(spectrum[in_band_mask].sum())
    out_band_power = float(spectrum[out_band_mask].sum())

    assert in_band_power > 0.0
    # If the Butterworth filtering were a no-op, the 10 Hz and 0.1 Hz tones
    # would carry roughly as much power as the 1.2 Hz tone (ratio ~= 2.0);
    # a real band-pass should crush them to a small fraction of it.
    assert out_band_power < 0.05 * in_band_power


def test_hr_from_signal_recovers_injected_frequency():
    fps = 30.0
    t = np.arange(0, 15, 1 / fps)
    sig = np.sin(2 * np.pi * 1.2 * t)  # exactly 72 bpm
    hr, snr, dominance = hr_from_signal(sig, fps)
    assert hr is not None
    assert abs(hr - 72.0) < 3.0
    assert dominance > 0.5
    assert snr > 3.0


def test_hr_from_signal_none_when_too_short():
    fps = 30.0
    sig = np.sin(np.arange(0, 1.0, 1 / fps))  # 1s < 2s minimum
    hr, snr, dominance = hr_from_signal(sig, fps)
    assert hr is None


def test_peak_dominance_discriminates_noise_from_clean_tone():
    fps = 30.0
    t = np.arange(0, 15, 1 / fps)
    clean_sig = np.sin(2 * np.pi * 1.2 * t)  # exactly 72 bpm, noiseless
    _, _, clean_dominance = hr_from_signal(clean_sig, fps)

    rng = np.random.RandomState(0)
    noise_sig = rng.randn(t.size)  # pure broadband noise, no dominant tone
    _, _, noise_dominance = hr_from_signal(noise_sig, fps)

    assert noise_dominance < 0.5
    assert noise_dominance < clean_dominance


def test_peak_dominance_is_stable_across_zero_padding_factors():
    # Regression test for a bug where peak_dominance (originally
    # peak_power / total_power) depended on the FFT zero-padding factor
    # (n_fft), which itself depends on the input signal length. The same
    # clean tone measured over different durations produced wildly
    # different dominance values purely due to padding, not signal quality.
    # peak_dominance must be (approximately) invariant to n_fft.
    fps = 30.0
    in_band_freq = 1.2  # 72 bpm

    t_short = np.arange(0, 8.0, 1 / fps)  # 240 samples
    t_long = np.arange(0, 40.0, 1 / fps)  # 1200 samples

    sig_short = np.sin(2 * np.pi * in_band_freq * t_short)
    sig_long = np.sin(2 * np.pi * in_band_freq * t_long)

    n_fft_short = int(2 ** np.ceil(np.log2(t_short.size * 4)))
    n_fft_long = int(2 ** np.ceil(np.log2(t_long.size * 4)))
    assert n_fft_short != n_fft_long  # sanity check: padding factors differ

    _, _, dominance_short = hr_from_signal(sig_short, fps)
    _, _, dominance_long = hr_from_signal(sig_long, fps)

    assert dominance_short > 0.5
    assert dominance_long > 0.5
    assert abs(dominance_short - dominance_long) < 0.1
