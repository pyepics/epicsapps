#!/usr/bin/env python
"""
Live areaDetector NTNDArray stream model for the PVA adviewer.
"""

import logging
import struct
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from threading import Event, Lock, Thread
from typing import Protocol

import bitshuffle
import blosc
import lz4.block
import numpy as np
from p4p.client.thread import Context, Subscription, WorkQueue

__all__ = ["ADViewerModel", "FrameModel", "StreamStatsModel", "StreamRatesModel"]

_log = logging.getLogger(__name__)

# Map areaDetector NTNDArray scalar-type code to (numpy dtype name, element size).
_SCALAR_TYPE_MAP: dict[int, tuple[str, int]] = {
    1: ("int8", 1),
    2: ("int16", 2),
    3: ("int32", 4),
    4: ("int64", 8),
    5: ("uint8", 1),
    6: ("uint16", 2),
    7: ("uint32", 4),
    8: ("uint64", 8),
    9: ("float32", 4),
    10: ("float64", 8),
}

_FRAME_ID_RESET_THRESHOLD = 1000
FrameObserver = Callable[["ADViewerModel"], None]


@dataclass(frozen=True)
class FrameModel:
    """A single decoded areaDetector frame plus per-frame metadata."""

    image: np.ndarray
    timestamp: float
    unique_id: int
    codec_name: str
    compressed_bytes: int
    uncompressed_bytes: int
    decode_time_ms: float
    attributes: dict[str, object]

    def __repr__(self) -> str:
        return (
            f"unique id={self.unique_id} shape={self.image.shape} "
            f"dtype={self.image.dtype} codec={self.codec_name!r} "
            f"compressed={self.compressed_bytes} B "
            f"uncompressed={self.uncompressed_bytes} B "
            f"decode={self.decode_time_ms:.1f} ms "
            f"timestamp={self.timestamp:.3f}"
        )


@dataclass
class StreamStatsModel:
    """Aggregate stream counters. Mutated under the model's lock."""

    frames_received: int = 0
    frames_dropped: int = 0
    frames_dropped_at_input: int = 0
    decode_errors: int = 0
    subscription_errors: int = 0
    uncompressed_bytes_total: int = 0
    first_unique_id: int = -1
    last_unique_id: int = -1
    last_update_wall_time: float = 0.0

    def snapshot(self) -> "StreamStatsModel":
        """Return a shallow copy safe to read outside the lock."""
        return replace(self)


@dataclass
class StreamRatesModel:
    """Derived rates computed from two `StreamStatsModel` snapshots."""

    fps: float
    drop_rate: float
    input_drop_rate: float
    throughput_mb_s: float
    decode_time_ms: float
    total_received: int
    total_dropped: int
    last_unique_id: int

    @classmethod
    def between(
        cls,
        prev: StreamStatsModel,
        curr: StreamStatsModel,
        elapsed_s: float,
        last_decode_time_ms: float,
    ) -> "StreamRatesModel":
        dt = max(elapsed_s, 1e-9)
        return cls(
            fps=(curr.frames_received - prev.frames_received) / dt,
            drop_rate=(curr.frames_dropped - prev.frames_dropped) / dt,
            input_drop_rate=(curr.frames_dropped_at_input - prev.frames_dropped_at_input) / dt,
            throughput_mb_s=(curr.uncompressed_bytes_total - prev.uncompressed_bytes_total) / dt / 1e6,
            decode_time_ms=last_decode_time_ms,
            total_received=curr.frames_received,
            total_dropped=curr.frames_dropped,
            last_unique_id=curr.last_unique_id,
        )


class FrameCallback(Protocol):
    """Protocol for callbacks that receive a new decoded detector frame."""

    def __call__(self, frame: FrameModel) -> None: ...


class _LatestSlot:
    """One-element mailbox. New puts overwrite (and report) the prior value."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._value: object | None = None
        self._has_value = Event()

    def put(self, value: object) -> bool:
        """Store *value*. Returns True if a prior value was overwritten."""
        with self._lock:
            overwritten = self._value is not None
            self._value = value
        self._has_value.set()
        return overwritten

    def take(self, timeout: float | None = None) -> object | None:
        """Block until a value is available, then return and clear it."""
        if not self._has_value.wait(timeout=timeout):
            return None
        with self._lock:
            value, self._value = self._value, None
            if value is not None:
                self._has_value.clear()
        return value

    def wake(self) -> None:
        """Unblock any waiting consumers (used on shutdown)."""
        self._has_value.set()


def _decompress_payload(
    compressed_bytes: bytes,
    codec_name: str,
    scalar_type: int,
    compressed_size: int,
    uncompressed_size: int,
) -> np.ndarray:
    """Decompress a compressed NTNDArray payload into a 1-D numpy array."""
    dtype, elem_size = _SCALAR_TYPE_MAP.get(scalar_type, ("uint8", 1))
    chunk = compressed_bytes[:compressed_size]

    if codec_name == "zlib":
        return np.frombuffer(zlib.decompress(chunk), dtype=dtype)

    if codec_name == "lz4hdf5":
        orig_size = struct.unpack_from(">Q", chunk, 0)[0]
        block_size = struct.unpack_from(">I", chunk, 8)[0]
        out_parts: list[bytes] = []
        pos, write_pos = 12, 0
        while write_pos < orig_size:
            comp_block_size = struct.unpack_from(">I", chunk, pos)[0]
            pos += 4
            current_block = min(block_size, orig_size - write_pos)
            if comp_block_size == current_block:
                out_parts.append(chunk[pos : pos + current_block])
            else:
                out_parts.append(lz4.block.decompress(chunk[pos : pos + comp_block_size], uncompressed_size=current_block))
            pos += comp_block_size
            write_pos += current_block
        return np.frombuffer(b"".join(out_parts), dtype=dtype)

    if codec_name == "blosc":
        return np.frombuffer(blosc.decompress(chunk), dtype=dtype)

    if codec_name == "lz4":
        return np.frombuffer(lz4.block.decompress(chunk, uncompressed_size=uncompressed_size), dtype=dtype)

    if codec_name == "bslz4":
        n_elem = uncompressed_size // elem_size
        out = bitshuffle.decompress_lz4(np.frombuffer(chunk, dtype=np.uint8), (n_elem,), np.dtype(dtype))
        return out.reshape(-1)

    raise RuntimeError(f"Unsupported codec: {codec_name!r}")


class ADViewerModel:
    """Live areaDetector NTNDArray stream model."""

    def __init__(
        self,
        num_decoder_threads: int = 2,
        work_queue_size: int = 4096,
        join_timeout: float = 2.0,
    ) -> None:
        self.num_decoder_threads = num_decoder_threads
        self.work_queue_size = work_queue_size
        self.join_timeout = join_timeout

        self._context: Context = Context("pva", nt=False)
        self._pv_name: str = ""
        self._frame_callback: FrameCallback | None = None
        self._subscription: Subscription | None = None
        self._work_queue: WorkQueue | None = None
        self._monitor_thread: Thread | None = None
        self._decoder_threads: list[Thread] = []

        self._slot = _LatestSlot()
        self._stop_event = Event()

        self._lock = Lock()
        self._frame: FrameModel | None = None
        self._stats = StreamStatsModel()
        self._observers: list[FrameObserver] = []
        self._last_roi_max_intensity: float | None = None
        self._has_roi: bool = False
        self._max_intensity_observers: list[Callable[[float | None], None]] = []

    @property
    def pv_name(self) -> str:
        """The PV name of the active subscription (empty if not subscribed)."""
        with self._lock:
            return self._pv_name

    @property
    def is_subscribed(self) -> bool:
        """Whether a live monitor subscription is currently active."""
        with self._lock:
            return self._subscription is not None

    @property
    def frame(self) -> FrameModel | None:
        """The most recently accepted frame, or None if none have arrived."""
        with self._lock:
            return self._frame

    @property
    def stats(self) -> StreamStatsModel:
        """A consistent snapshot of the current stream counters."""
        with self._lock:
            return self._stats.snapshot()

    @property
    def last_roi_max_intensity(self) -> float | None:
        """The most recent ROI/integration max intensity, or None if unavailable."""
        with self._lock:
            return self._last_roi_max_intensity

    @property
    def has_roi(self) -> bool:
        """Whether an ROI is currently drawn on the image canvas."""
        with self._lock:
            return self._has_roi

    def set_last_roi_max_intensity(self, value: float | None) -> None:
        """Publish a new ROI/integration max intensity (callable from any thread)."""
        with self._lock:
            self._last_roi_max_intensity = value
            self._has_roi = True
            observers = list(self._max_intensity_observers)
        for cb in observers:
            try:
                cb(value)
            except Exception:
                pass

    def clear_last_roi_max_intensity(self) -> None:
        """Reset the ROI max snapshot to None (e.g. when ROI is cleared)."""
        with self._lock:
            self._last_roi_max_intensity = None
            self._has_roi = False
            observers = list(self._max_intensity_observers)
        for cb in observers:
            try:
                cb(None)
            except Exception:
                pass

    def add_max_intensity_observer(self, callback: Callable[[float | None], None]) -> None:
        """Register *callback* to be invoked whenever the ROI max changes."""
        with self._lock:
            self._max_intensity_observers.append(callback)

    def remove_max_intensity_observer(self, callback: Callable[[float | None], None]) -> None:
        """Unregister a previously added max-intensity observer."""
        with self._lock:
            if callback in self._max_intensity_observers:
                self._max_intensity_observers.remove(callback)

    def add_observer(self, callback: FrameObserver) -> None:
        """Register a callback fired after each successfully stored frame."""
        with self._lock:
            self._observers.append(callback)

    def remove_observer(self, callback: FrameObserver) -> None:
        """Unregister a previously added observer callback."""
        with self._lock:
            if callback in self._observers:
                self._observers.remove(callback)

    def subscribe(self, pv_name: str, frame_callback: FrameCallback) -> None:
        """Start monitoring *pv_name* and deliver `FrameModel`s to *frame_callback*."""
        self.unsubscribe()
        with self._lock:
            self._pv_name = pv_name
            self._frame_callback = frame_callback
            self._stats = StreamStatsModel()
            self._frame = None
            self._stop_event.clear()

            self._work_queue = WorkQueue(maxsize=self.work_queue_size)
            self._monitor_thread = Thread(
                target=self._work_queue.handle,
                name=f"ADViewerMonitor[{pv_name}]",
                daemon=True,
            )
            self._monitor_thread.start()

            self._decoder_threads = [Thread(target=self._decoder_loop, name=f"ADViewerDecoder[{pv_name}]-{i}", daemon=True) for i in range(self.num_decoder_threads)]
            for t in self._decoder_threads:
                t.start()

            _log.info("AD viewer subscribing to %s via p4p monitor (decoders=%d)", pv_name, self.num_decoder_threads)
            self._subscription = self._context.monitor(
                pv_name,
                self._on_update,
                request="",
                notify_disconnect=True,
                queue=self._work_queue,
            )

    def unsubscribe(self) -> None:
        """Tear down the active subscription (if any) and stop all worker threads."""
        with self._lock:
            subscription = self._subscription
            work_queue = self._work_queue
            monitor_thread = self._monitor_thread
            decoder_threads = self._decoder_threads
            self._subscription = None
            self._work_queue = None
            self._monitor_thread = None
            self._decoder_threads = []
            self._pv_name = ""
            self._frame_callback = None

        if subscription is None and not decoder_threads:
            return

        if subscription is not None:
            try:
                subscription.close()
            except Exception:
                _log.exception("Error closing PVA subscription")

        if work_queue is not None:
            try:
                work_queue.interrupt()
            except Exception:
                _log.exception("Error interrupting monitor WorkQueue")
            if monitor_thread is not None:
                monitor_thread.join(timeout=self.join_timeout)

        self._stop_event.set()
        self._slot.wake()
        for t in decoder_threads:
            t.join(timeout=self.join_timeout)

    def shutdown(self) -> None:
        """Fully release PVA resources. Call on application exit."""
        self.unsubscribe()
        try:
            self._context.close()
        except Exception:
            _log.exception("Error closing PVA context")

    def _record_input_drop(self) -> None:
        with self._lock:
            self._stats.frames_dropped_at_input += 1

    def _record_decode_error(self) -> None:
        with self._lock:
            self._stats.decode_errors += 1

    def _record_subscription_error(self) -> None:
        with self._lock:
            self._stats.subscription_errors += 1

    def _store_frame(self, frame: FrameModel) -> None:
        """Store *frame* if it is newer than what we already have, then notify."""
        with self._lock:
            stats = self._stats
            is_reset = stats.last_unique_id >= 0 and frame.unique_id < stats.last_unique_id - _FRAME_ID_RESET_THRESHOLD
            if is_reset:
                stats.first_unique_id = frame.unique_id
                stats.last_unique_id = -1

            if frame.unique_id <= stats.last_unique_id:
                return

            if stats.first_unique_id < 0:
                stats.first_unique_id = frame.unique_id
            elif stats.last_unique_id >= 0:
                gap = frame.unique_id - stats.last_unique_id - 1
                if gap > 0:
                    stats.frames_dropped += gap

            self._frame = frame
            stats.frames_received += 1
            stats.uncompressed_bytes_total += frame.uncompressed_bytes
            stats.last_unique_id = frame.unique_id
            stats.last_update_wall_time = time.time()

            callback = self._frame_callback
            observers = list(self._observers)

        # Fire callback + observers outside the lock so user code can call back into us.
        if callback is not None:
            try:
                callback(frame)
            except Exception:
                _log.exception("Frame callback raised")
        for obs in observers:
            try:
                obs(self)
            except Exception:
                _log.exception("Observer raised")

    def _on_update(self, value: object) -> None:
        """p4p monitor callback (runs on the WorkQueue thread). Hand the latest value off to the decoder pool."""
        if isinstance(value, Exception):
            self._record_subscription_error()
            _log.debug("PVA subscription error on %s: %r", self._pv_name, value)
            return
        if self._slot.put(value):
            self._record_input_drop()

    def _decoder_loop(self) -> None:
        """Worker loop: pull the latest pending value, decode, store & notify."""
        while not self._stop_event.is_set():
            value = self._slot.take(timeout=0.5)
            if self._stop_event.is_set():
                return
            if value is None:
                continue
            frame = self._decode_value(value)
            if frame is not None:
                self._store_frame(frame)

    def _decode_value(self, value: object) -> FrameModel | None:
        """Build a `FrameModel` from a raw PVA Value, or None on decode error."""
        if value["value"] is None:
            return None
        decode_start = time.perf_counter()
        try:
            image, codec_name, compressed_size, uncompressed_size = self._decode_image(value)
        except Exception:
            self._record_decode_error()
            _log.exception("Error decoding NTNDArray frame on %s", self._pv_name)
            return None
        decode_time_ms = (time.perf_counter() - decode_start) * 1000.0

        try:
            ts = value["dataTimeStamp"]
            timestamp = float(ts["secondsPastEpoch"]) + float(ts["nanoseconds"]) * 1e-9
        except Exception:
            timestamp = time.time()

        try:
            unique_id = int(value["uniqueId"])
        except Exception:
            unique_id = -1

        return FrameModel(
            image=image,
            timestamp=timestamp,
            unique_id=unique_id,
            codec_name=codec_name,
            compressed_bytes=compressed_size,
            uncompressed_bytes=uncompressed_size,
            decode_time_ms=decode_time_ms,
            attributes=self._extract_attributes(value),
        )

    @staticmethod
    def _decode_image(value: object) -> tuple[np.ndarray, str, int, int]:
        """Decode an NTNDArray Value into a numpy image plus codec / size metadata."""

        raw = value["value"]
        if raw is None:
            raise RuntimeError("NTNDArray has no value")
        dims: list[int] = [d["size"] for d in value["dimension"] if d["size"] > 0]
        if not dims:
            raise RuntimeError("NTNDArray has empty dimensions")
        shape = tuple(dims[::-1])

        flat = np.array(raw, copy=False)
        if flat.size == 0:
            raise RuntimeError("NTNDArray value buffer is empty")
        _log.info(f"Raw PVA array (before decompression): dtype={flat.dtype}, size={flat.size}, nbytes={flat.nbytes}")

        codec_name: str = ""
        try:
            codec_name = value["codec"]["name"] or ""
        except Exception:
            codec_name = ""

        try:
            compressed_size = int(value["compressedSize"])
        except Exception:
            compressed_size = int(flat.nbytes)
        try:
            uncompressed_size = int(value["uncompressedSize"])
        except Exception:
            uncompressed_size = int(flat.nbytes)

        if codec_name:
            try:
                raw_param = value["codec"]["parameters"]
                scalar_type = int(raw_param) if raw_param is not None else 5
            except Exception:
                scalar_type = 5
            _log.info(f"Decompressing with codec={codec_name!r}, scalar_type={scalar_type}, compressed_size={compressed_size}, uncompressed_size={uncompressed_size}")
            flat = _decompress_payload(flat.tobytes(), codec_name, scalar_type, compressed_size, uncompressed_size)
            _log.info(f"Decompressed array: dtype={flat.dtype}, min={flat.min()}, max={flat.max()}, shape={flat.shape}")

        image = flat.reshape(shape)
        _log.info(f"Reshaped image: dtype={image.dtype}, min={image.min()}, max={image.max()}, shape={image.shape}")
        if image.ndim == 3:
            if image.shape[0] in (3, 4):
                image = np.moveaxis(image, 0, -1)
            elif image.shape[1] in (3, 4):
                image = np.swapaxes(image, 1, 2)
                image = np.moveaxis(image, 0, -1)
        return image, codec_name, compressed_size, uncompressed_size

    @staticmethod
    def _extract_attributes(value: object) -> dict[str, object]:
        """Pull areaDetector NDAttributes out of the NTNDArray into a dict."""
        try:
            ad_attributes = value.get("attribute")
        except Exception:
            return {}
        if ad_attributes is None:
            return {}
        attributes: dict[str, object] = {}
        for attr in ad_attributes:
            try:
                attributes[attr["name"]] = attr["value"]
            except Exception:
                continue
        return attributes
