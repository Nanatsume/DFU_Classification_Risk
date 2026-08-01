"""Capture abstraction — the ONE place the real camera plugs in later.

Everything else (server, saving, JSON, manifest, front-end) is written against this interface and
already works today with SimulatedSource. When the USB cameras arrive, implement UsbCameraSource
and set CAPTURE_SOURCE=usb. Nothing else changes.

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


class UsbCameraSource(CaptureSource):
    """TODO — real USB capture. Implement this when the devices arrive; it is the only new code.

    podoscope: an ordinary USB webcam.
        cap = cv2.VideoCapture(PODO_INDEX)
        ok, frame = cap.read()
        return cv2.imencode('.png', frame)[1].tobytes()

    thermal: a radiometric USB device. Grab the colourised frame for the PNG here, and ALSO pull
        the temperature array through the vendor SDK and save it next to the PNG
        (e.g. data/{rid}/{rid}_thermal.tiff). The colourised PNG alone loses the temperatures.
    """

    def grab(self, modality: str, rid: str) -> bytes:
        raise NotImplementedError(
            "UsbCameraSource is not implemented yet. Set CAPTURE_SOURCE=sim until the devices "
            "arrive, then implement this method (cv2 for podoscope, vendor SDK for thermal)."
        )


def get_source() -> CaptureSource:
    kind = os.environ.get("CAPTURE_SOURCE", "sim").lower()
    return UsbCameraSource() if kind == "usb" else SimulatedSource()
