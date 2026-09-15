"""The foot-pair sanity check in separate_and_crop_feet().

These build the connected-component mask directly instead of running HMRF-EM, so they take
milliseconds rather than a minute per image and pin the decision rule itself rather than the
segmentation that feeds it.

Why the rule exists: taking the two largest components on faith turns a bad capture from useless
into dangerous. On real captures from the rig, a bright window or the edge of the glass survived
segmentation, was picked as the "second foot", and the pipeline reported success — the wrong image
then gets filed against a patient's research id with nothing in the log to show for it.

Thresholds were calibrated on real podoscope captures: a good one measured balance 0.963 with each
foot covering ~14% of the frame; one whose second region was the edge of the glass measured
balance 0.142 with 4.3% coverage.
"""
from __future__ import annotations

import numpy as np
import pytest

import preprocessing as pp

H = W = 400
FRAME = H * W


def mask_with(*boxes) -> tuple[np.ndarray, np.ndarray]:
    """Build a (H, W) component mask from (y0, y1, x0, x1) boxes, plus a matching RGB image.

    Boxes must not touch, or they merge into one component and the test measures the wrong thing.
    """
    mask = np.zeros((H, W), dtype=bool)
    for y0, y1, x0, x1 in boxes:
        mask[y0:y1, x0:x1] = True
    img = np.repeat((mask.astype(np.uint8) * 200)[:, :, None], 3, axis=2)
    return mask, img


def test_two_matched_feet_are_accepted():
    """The shape of a good capture: two similar regions, each a healthy share of the frame."""
    mask, img = mask_with((50, 350, 40, 180), (50, 350, 220, 360))
    left, right = pp.separate_and_crop_feet(mask, img)
    assert left is not None and right is not None
    # Each region here is 300x140 = 10.5% of the frame, balance 1.0 — comfortably inside both limits.
    assert abs(left.shape[0] - right.shape[0]) <= 2


def test_slightly_uneven_feet_still_accepted():
    """Real feet are not pixel-identical — the good capture measured 0.963, not 1.0."""
    mask, img = mask_with((50, 350, 40, 180), (50, 340, 220, 355))
    left, right = pp.separate_and_crop_feet(mask, img)
    assert left is not None and right is not None


def test_tiny_second_region_is_rejected():
    """The real failure: a glass edge / reflection picked up as the second foot."""
    mask, img = mask_with((50, 350, 40, 180), (60, 100, 300, 330))
    with pytest.raises(pp.SegmentationError) as e:
        pp.separate_and_crop_feet(mask, img)
    assert "pair of feet" in str(e.value)


def test_single_region_is_rejected():
    """Both feet merged into one blob — there is no second foot to return."""
    mask, img = mask_with((50, 350, 40, 360))
    with pytest.raises(pp.SegmentationError) as e:
        pp.separate_and_crop_feet(mask, img)
    assert "one region" in str(e.value)


def test_two_specks_are_rejected_even_though_balanced():
    """Balance alone is not enough: two equally tiny regions are balanced but are not feet."""
    mask, img = mask_with((10, 40, 10, 40), (10, 40, 100, 130))
    with pytest.raises(pp.SegmentationError):
        pp.separate_and_crop_feet(mask, img)


def test_rejection_message_names_the_measurements():
    """The nurse is still standing next to the patient — the message has to say what to do."""
    mask, img = mask_with((50, 350, 40, 180), (60, 100, 300, 330))
    with pytest.raises(pp.SegmentationError) as e:
        pp.separate_and_crop_feet(mask, img)
    msg = str(e.value)
    assert "balance" in msg
    assert "Re-take" in msg or "re-take" in msg


def test_thresholds_are_tunable(monkeypatch):
    """A rig with different framing must be able to loosen this without editing the pipeline."""
    mask, img = mask_with((50, 350, 40, 180), (60, 100, 300, 330))
    with pytest.raises(pp.SegmentationError):
        pp.separate_and_crop_feet(mask, img)
    monkeypatch.setattr(pp, "MIN_FOOT_BALANCE", 0.01)   # measured balance here is 0.029
    monkeypatch.setattr(pp, "MIN_FOOT_COVERAGE", 0.001)  # measured coverage here is 0.008
    left, right = pp.separate_and_crop_feet(mask, img)
    assert left is not None and right is not None
