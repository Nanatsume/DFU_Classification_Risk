"""Camera selection. These tests never touch real hardware — the DirectShow device list is
monkeypatched — so they run the same on CI and on a machine with nothing plugged in.

What is worth testing here is not "does the webcam work" (only a human looking at the image can
answer that) but the selection logic, because its failure mode is silent: a virtual camera opens
fine and returns frames, so picking the wrong device produces a plausible-looking photo filed
under a real patient's research id.
"""
from __future__ import annotations

import pytest

import capture_source as cs

# What this workstation actually enumerates: two real cameras and four virtual ones.
DEVICES = [
    "FHD Webcam",                  # built-in laptop camera
    "Logi C615 HD WebCam",         # the podoscope camera
    "LSVCam",                      # virtual
    "Logi Capture",                # virtual — returns a "camera disabled" placeholder image
    "Camera (NVIDIA Broadcast)",   # virtual
    "OBS Virtual Camera",          # virtual
]


@pytest.fixture()
def devices(monkeypatch):
    monkeypatch.setattr(cs, "enumerate_video_devices", lambda: (list(DEVICES), None))
    monkeypatch.setattr(cs, "PODO_CAMERA_INDEX", "")
    monkeypatch.setattr(cs, "PODO_CAMERA_NAME", "Logi C615")
    return DEVICES


def test_resolves_the_podoscope_by_name(devices):
    assert cs.resolve_podoscope_index() == 1


def test_name_match_is_case_insensitive_and_partial(devices, monkeypatch):
    monkeypatch.setattr(cs, "PODO_CAMERA_NAME", "logi c615")
    assert cs.resolve_podoscope_index() == 1


def test_does_not_fall_back_to_a_virtual_camera(devices, monkeypatch):
    """Regression guard: when the podoscope is unplugged the answer is an error, never index 0 or
    the first camera that happens to open. A silent fallback would file the laptop webcam's view
    of the room as a patient's foot."""
    monkeypatch.setattr(cs, "enumerate_video_devices",
                        lambda: ([d for d in DEVICES if "C615" not in d], None))
    with pytest.raises(cs.CaptureError) as e:
        cs.resolve_podoscope_index()
    assert "Logi C615" in str(e.value)
    assert "OBS Virtual Camera" in str(e.value)  # the message lists what it did see


def test_explicit_index_overrides_the_name_lookup(devices, monkeypatch):
    monkeypatch.setattr(cs, "PODO_CAMERA_INDEX", "3")
    assert cs.resolve_podoscope_index() == 3


def test_explicit_index_works_without_device_enumeration(monkeypatch):
    """The escape hatch has to work on a machine where pygrabber is missing — that is its job."""
    monkeypatch.setattr(cs, "enumerate_video_devices", lambda: ([], "pygrabber is not installed"))
    monkeypatch.setattr(cs, "PODO_CAMERA_INDEX", "2")
    assert cs.resolve_podoscope_index() == 2


def test_no_enumeration_and_no_index_is_an_actionable_error(monkeypatch):
    """The reason is carried through rather than flattened into "no cameras". Enumeration failing
    (COM not initialised on a FastAPI worker thread, say) and no camera being attached produce the
    same empty list, and telling someone to plug in a camera that is already plugged in wastes the
    minute when a patient is waiting."""
    monkeypatch.setattr(cs, "enumerate_video_devices",
                        lambda: ([], "OSError: CoInitialize has not been called"))
    monkeypatch.setattr(cs, "PODO_CAMERA_INDEX", "")
    with pytest.raises(cs.CaptureError) as e:
        cs.resolve_podoscope_index()
    assert "PODO_CAMERA_INDEX" in str(e.value)
    assert "CoInitialize" in str(e.value)        # the real cause survives to the message


def test_get_source_honours_capture_source_env(monkeypatch):
    monkeypatch.setenv("CAPTURE_SOURCE", "usb")
    assert isinstance(cs.get_source(), cs.UsbCameraSource)
    monkeypatch.setenv("CAPTURE_SOURCE", "sim")
    assert isinstance(cs.get_source(), cs.SimulatedSource)
    monkeypatch.delenv("CAPTURE_SOURCE")
    assert isinstance(cs.get_source(), cs.SimulatedSource)  # safe default: never the real camera


def test_thermal_is_still_unimplemented_and_says_what_is_missing():
    with pytest.raises(NotImplementedError) as e:
        cs.UsbCameraSource().grab("thermal", "P0001")
    msg = str(e.value)
    assert "radiometric" in msg  # the part that is easy to forget when wiring the SDK up
