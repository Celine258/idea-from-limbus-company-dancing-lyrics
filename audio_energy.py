"""Cheap RMS analysis; no FFT or extra decoder is needed for the MVP."""
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtMultimedia import QAudioBuffer, QAudioFormat


def pcm_rms(data, sample_format: QAudioFormat.SampleFormat) -> float:
    formats = {
        QAudioFormat.SampleFormat.UInt8: (np.uint8, 128.0, 128.0),
        QAudioFormat.SampleFormat.Int16: (np.int16, 0.0, 32768.0),
        QAudioFormat.SampleFormat.Int32: (np.int32, 0.0, 2147483648.0),
        QAudioFormat.SampleFormat.Float: (np.float32, 0.0, 1.0),
    }
    if sample_format not in formats:
        raise ValueError("不支持的音频采样格式")
    dtype, center, divisor = formats[sample_format]
    samples = np.frombuffer(data, dtype=dtype)
    if not samples.size:
        return 0.0
    # Bound work to roughly 4096 samples even for large decoder buffers.
    samples = samples[::max(1, samples.size // 4096)].astype(np.float64)
    samples = (samples - center) / divisor
    return float(np.sqrt(np.mean(np.square(np.nan_to_num(samples)))))


class EnergyAnalyzer(QObject):
    received = Signal(float, float)  # normalized energy, media timestamp in ms
    failed = Signal(str)

    @Slot(QAudioBuffer)
    def process(self, buffer: QAudioBuffer):
        if not buffer.isValid() or buffer.byteCount() == 0:
            return
        try:
            # data() is a view owned by buffer; analysis completes within this callback.
            rms = pcm_rms(buffer.data(), buffer.format().sampleFormat())
            energy = min(1.0, max(0.0, rms * 3.2))
            self.received.emit(energy, buffer.startTime() / 1000.0)
        except (ValueError, TypeError, BufferError) as error:
            self.failed.emit(str(error))
