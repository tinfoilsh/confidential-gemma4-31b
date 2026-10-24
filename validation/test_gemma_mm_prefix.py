"""Preserve Gemma image attention when the image exceeds the local window."""

import pytest

from vllm.multimodal.inputs import MultiModalFeatureSpec, PlaceholderRange
from vllm.v1.worker.gpu.attn_utils import compute_mm_prefix_ranges

SLIDING_WINDOW = 1024
HIGH_RESOLUTION_EMBEDS = 1104
IMAGE_OFFSET = 100
IMAGE_SEPARATOR_TOKENS = 2
REQUEST_ID = "image_request"


def feature(length, offset=IMAGE_OFFSET, modality="image"):
    return MultiModalFeatureSpec(
        data=None, modality=modality, identifier=f"{modality}-{offset}",
        mm_position=PlaceholderRange(offset=offset, length=length),
    )


@pytest.mark.parametrize("modality", ["image", "video"])
def test_large_image_range_survives_for_kernel_clamped_models(modality):
    item = feature(HIGH_RESOLUTION_EMBEDS, modality=modality)
    ranges = compute_mm_prefix_ranges(
        [REQUEST_ID], {REQUEST_ID: [item]}, SLIDING_WINDOW, clamp_in_kernel=True
    )
    assert ranges == {0: [(IMAGE_OFFSET, IMAGE_OFFSET + HIGH_RESOLUTION_EMBEDS - 1)]}


def test_other_models_still_skip_ranges_larger_than_the_window():
    item = feature(HIGH_RESOLUTION_EMBEDS)
    assert compute_mm_prefix_ranges(
        [REQUEST_ID], {REQUEST_ID: [item]}, SLIDING_WINDOW
    ) == {0: []}


@pytest.mark.parametrize("length", [SLIDING_WINDOW - 1, SLIDING_WINDOW])
@pytest.mark.parametrize("clamp_in_kernel", [False, True])
def test_ranges_at_or_below_the_window_are_retained(length, clamp_in_kernel):
    item = feature(length)
    assert compute_mm_prefix_ranges(
        [REQUEST_ID], {REQUEST_ID: [item]}, SLIDING_WINDOW,
        clamp_in_kernel=clamp_in_kernel,
    ) == {0: [(IMAGE_OFFSET, IMAGE_OFFSET + length - 1)]}


def test_unbounded_attention_retains_large_images():
    item = feature(HIGH_RESOLUTION_EMBEDS)
    assert compute_mm_prefix_ranges([REQUEST_ID], {REQUEST_ID: [item]}) == {
        0: [(IMAGE_OFFSET, IMAGE_OFFSET + HIGH_RESOLUTION_EMBEDS - 1)]
    }


def test_requests_and_images_keep_separate_ranges_and_audio_is_excluded():
    second_offset = IMAGE_OFFSET + HIGH_RESOLUTION_EMBEDS + IMAGE_SEPARATOR_TOKENS
    items = [feature(HIGH_RESOLUTION_EMBEDS), feature(SLIDING_WINDOW, second_offset),
             feature(SLIDING_WINDOW, modality="audio")]
    assert compute_mm_prefix_ranges(
        ["no_media", REQUEST_ID], {REQUEST_ID: items}, SLIDING_WINDOW,
        clamp_in_kernel=True,
    ) == {0: [], 1: [(IMAGE_OFFSET, IMAGE_OFFSET + HIGH_RESOLUTION_EMBEDS - 1),
                    (second_offset, second_offset + SLIDING_WINDOW - 1)]}
