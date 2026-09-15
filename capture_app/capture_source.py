"""Capture abstraction — the ONE place the real camera plugs in.

Everything else (server, saving, JSON, manifest, front-end) is written against this interface.
SimulatedSource needs no hardware; UsbCameraSource talks to the real devices — podoscope is
implemented (Logitech C615 over USB), thermal still waits on the vendor SDK. Pick one with
CAPTURE_SOURCE=sim|usb; nothing else in the app changes.

    grab(modality, rid) -> PNG bytes

`modality` is "podoscope" or "thermal". For thermal the real device must also persist the
radiometric temperature array (see UsbCameraSource.grab).
"""
from __future__ import annotations
import io
import os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=7))


def _stamp() -> str:
    return datetime.now(TZ).strftime("%H:%M:%S")


class CaptureSource:
    def grab(self, modality: str, rid: str) -> bytes:
        raise NotImplementedError


SAMPLE_PODO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample", "P001.png")


class SimulatedSource(CaptureSource):
    """Stands in for the USB cameras with no hardware. The podoscope returns a real sample
    footprint so the preprocessing pipeline produces meaningful output for QC and the demo;
    the thermal returns a labelled placeholder."""

    def grab(self, modality: str, rid: str) -> bytes:
        from PIL import Image, ImageDraw
        if modality == "podoscope" and os.path.exists(SAMPLE_PODO):
            with open(SAMPLE_PODO, "rb") as f:
                return f.read()
        W, H = 640, 480
        img = Image.new("RGB", (W, H), (11, 15, 22))
        d = ImageDraw.Draw(img)
        if modality == "podoscope":
            for cx in (250, 390):
                d.ellipse([cx - 46, 120, cx + 46, 360], fill=(30, 44, 62))
            d.text((250, 40), "PODOSCOPE", fill=(150, 180, 215))
        else:
            for y in range(H):  # crude vertical thermal gradient
                t = y / H
                col = (int(20 + 200 * t), int(30 + 120 * (1 - abs(t - .5) * 2)), int(120 * (1 - t)))
                d.line([(0, y), (W, y)], fill=col)
            d.text((250, 40), "THERMAL (radiometric sim)", fill=(255, 255, 255))
        d.text((16, 456), f"{rid}  {_stamp()}", fill=(230, 230, 230))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


class CaptureError(RuntimeError):
    """Capture failed for a reason the nurse can act on (camera unplugged, wrong device selected,
    lens covered). server.py turns this into an HTTP error whose message is shown in the UI."""


# ---------- device selection ----------
# The workstation has more cameras than you would expect: the built-in laptop webcam, the Windows
# Hello IR sensor, and — on this machine — four *virtual* cameras (LSVCam, Logi Capture, NVIDIA
# Broadcast, OBS). That matters because a virtual camera opens cleanly and returns frames, so
# isOpened() and read() both succeed while the "photo" is really a software placeholder image.
# Selecting by index alone is therefore unsafe: DirectShow indices shift whenever a virtual camera
# starts or a USB device is replugged, and the failure mode is silent — the wrong image gets filed
# under a real research id with nothing in the log to show for it. So: match on the device name,
# every time, and keep an explicit index as the escape hatch.
PODO_CAMERA_NAME = os.environ.get("PODO_CAMERA_NAME", "Logi C615")
PODO_CAMERA_INDEX = os.environ.get("PODO_CAMERA_INDEX", "")
PODO_WIDTH = int(os.environ.get("PODO_CAMERA_WIDTH", "1920"))
PODO_HEIGHT = int(os.environ.get("PODO_CAMERA_HEIGHT", "1080"))
# This unit hands back black frames for the first several reads while auto-exposure settles;
# measured here ~8 is enough, 20 is comfortable and costs well under a second.
PODO_WARMUP_FRAMES = int(os.environ.get("PODO_CAMERA_WARMUP", "20"))
# A lens cap, an unlit podoscope box, or a virtual camera's placeholder all yield a near-uniform
# frame. Std-dev of a real foot image is far above this.
BLANK_FRAME_STD = float(os.environ.get("PODO_CAMERA_BLANK_STD", "3.0"))


def list_video_devices() -> list[str]:
    """DirectShow device names, indexed the same way `cv2.VideoCapture(i, CAP_DSHOW)` indexes
    them. Returns [] when the backend is unavailable (not Windows, or pygrabber not installed) —
    callers must read that as "cannot verify", not as "no cameras attached"."""
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        return []
    try:
        return list(FilterGraph().get_input_devices())
    except Exception:
        return []


def resolve_podoscope_index() -> int:
    """Which cv2 index is the podoscope camera, right now.

    Re-resolved on every capture rather than cached at startup: a camera replugged mid-clinic
    changes the index underneath a long-running server, and the lookup costs milliseconds."""
    if PODO_CAMERA_INDEX.strip():
        return int(PODO_CAMERA_INDEX)
    devices = list_video_devices()
    if not devices:
        raise CaptureError(
            "Cannot enumerate cameras to identify the podoscope (pygrabber not installed, or not "
            "on Windows). Set PODO_CAMERA_INDEX to the camera's cv2 index to bypass the lookup."
        )
    wanted = PODO_CAMERA_NAME.lower()
    for i, name in enumerate(devices):
        if wanted in name.lower():
            return i
    seen = ", ".join(f"[{i}] {n}" for i, n in enumerate(devices))
    raise CaptureError(
        f"No camera matching {PODO_CAMERA_NAME!r} is connected. Cameras seen: {seen}. "
        "Plug the podoscope in, or set PODO_CAMERA_NAME / PODO_CAMERA_INDEX."
    )


class UsbCameraSource(CaptureSource):
    """Real USB capture. Podoscope is implemented; thermal waits on the device's SDK.

    Run with CAPTURE_SOURCE=usb. Nothing outside this class changes.
    """

    def grab(self, modality: str, rid: str) -> bytes:
        if modality == "podoscope":
            return self._grab_podoscope()
        raise NotImplementedError(
            "Thermal capture needs the vendor SDK, which is not wired up yet (device on order). "
            "Run with CAPTURE_SOURCE=sim to keep the placeholder, and implement _grab_thermal() "
            "when the camera arrives: return the colourised frame as PNG here AND persist the "
            "radiometric temperature array to data/thermal/{rid}/radiometric/ — the colourised "
            "PNG alone throws away the temperatures, which is the whole point of the modality."
        )

    def _grab_podoscope(self) -> bytes:
        import cv2
        import numpy as np

        index = resolve_podoscope_index()
        # CAP_DSHOW: Windows' default MSMF backend is slower to open on this camera and ignores
        # some resolution requests. Off Windows, let OpenCV choose.
        backend = getattr(cv2, "CAP_DSHOW", 0) if os.name == "nt" else 0
        cap = cv2.VideoCapture(index, backend)
        try:
            if not cap.isOpened():
                raise CaptureError(
                    f"Camera [{index}] ({PODO_CAMERA_NAME}) could not be opened — another program "
                    "may hold it (Logi Capture, OBS, Teams). Close that program and retry."
                )
            # MJPG before the size: at 1920x1080 the uncompressed YUY2 stream is bandwidth-bound,
            # and setting the size first can leave the device pinned to a lower mode.
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, PODO_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, PODO_HEIGHT)

            frame = None
            for _ in range(PODO_WARMUP_FRAMES):
                ok, f = cap.read()
                if ok and f is not None:
                    frame = f
            if frame is None:
                raise CaptureError(
                    f"Camera [{index}] ({PODO_CAMERA_NAME}) opened but returned no frame. "
                    "Unplug it, plug it back in, and retry."
                )

            if float(np.asarray(frame).std()) < BLANK_FRAME_STD:
                raise CaptureError(
                    f"Camera [{index}] ({PODO_CAMERA_NAME}) returned a blank frame — check the "
                    "lens cover and that the podoscope light is on."
                )

            h, w = frame.shape[:2]
            if (w, h) != (PODO_WIDTH, PODO_HEIGHT):
                # Not fatal — the pipeline is resolution-agnostic. Logged because a silent drop to
                # 640x480 would quietly degrade every image collected from then on.
                print(f"[capture] warning: asked {PODO_WIDTH}x{PODO_HEIGHT}, got {w}x{h}")

            ok, buf = cv2.imencode(".png", frame)
            if not ok:
                raise CaptureError("Captured a frame but could not encode it as PNG.")
            return buf.tobytes()
        finally:
            cap.release()


def get_source() -> CaptureSource:
    kind = os.environ.get("CAPTURE_SOURCE", "sim").lower()
    return UsbCameraSource() if kind == "usb" else SimulatedSource()
