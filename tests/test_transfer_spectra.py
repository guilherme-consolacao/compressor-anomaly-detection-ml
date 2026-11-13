import numpy as np
import pytest

from compressor_anomaly_detection_ml.transfer_spectra import spectrum_signature


def test_rich_spectral_signature_preserves_energy_gain_invariance_and_harmonic_peak():
    frequency = np.arange(1025, dtype=float)
    density = np.exp(-(((frequency - 50) / 2) ** 2)) + 0.5 * np.exp(-(((frequency - 100) / 2) ** 2))
    signature = spectrum_signature(frequency, density)
    assert signature == pytest.approx(spectrum_signature(frequency, density * 19))
    assert sum(
        value for name, value in signature.items() if name.startswith("spectral_bin_")
    ) == pytest.approx(1.0)
    assert signature["harmonic_energy_1"] > 0.6
    assert signature["harmonic_energy_2"] > 0.3
    assert signature["dominant_low_frequency_relative"] == pytest.approx(0.3)
