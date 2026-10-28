"""Preserve image masks and graph routing across Blackwell batches."""

from types import SimpleNamespace
import unittest

import torch

from vllm.v1.attention.backend import AttentionCGSupport
from vllm.v1.attention.backends.triton_flashinfer import TritonDecodeRouting

SPECULATIVE_COUNTS = (4, 6)
GENERAL = 0
CAUSAL = 1
WINDOW = 1024


def routing(proposals, clamped=True):
    layer = SimpleNamespace(sliding_window=WINDOW, mm_prefix_clamp_sliding_window=clamped)
    config = SimpleNamespace(
        compilation_config=SimpleNamespace(static_forward_context={"local": layer}),
        speculative_config=SimpleNamespace(num_speculative_tokens=proposals, parallel_drafting=False),
        use_v2_model_runner=True,
    )
    return TritonDecodeRouting(["local"], config)


def metadata(lengths, ends, ranges):
    starts = [0]
    for length in lengths:
        starts.append(starts[-1] + length)
    return SimpleNamespace(max_query_len=max(lengths), query_start_loc_cpu=torch.tensor(starts),
                           seq_lens_cpu_upper_bound=torch.tensor(ends), mm_req_doc_ranges=ranges)


class PrefillRoutingTests(unittest.TestCase):
    def test_graph_support_preserves_the_image_window_constraint(self):
        for clamped, expected in ((True, AttentionCGSupport.UNIFORM_BATCH),
                                  (False, AttentionCGSupport.NEVER)):
            layer = SimpleNamespace(sliding_window=WINDOW, mm_prefix_clamp_sliding_window=clamped)
            config = SimpleNamespace(compilation_config=SimpleNamespace(static_forward_context={"local": layer}))
            self.assertEqual(TritonDecodeRouting.get_cudagraph_support(config, None), expected)

    def test_every_decode_width_uses_the_capture_child(self):
        for proposals in SPECULATIVE_COUNTS:
            policy = routing(proposals)
            for query in range(1, proposals + 2):
                for spans in ({}, {0: [(20, 100)]}, {0: [(100, 150)]}):
                    with self.subTest(proposals=proposals, query=query, spans=spans):
                        self.assertEqual(policy.select(metadata([query, 0], [128, 0], spans)),
                                         policy.capture_variant)

    def test_only_causal_large_prefills_use_flashinfer(self):
        policy = routing(max(SPECULATIVE_COUNTS))
        cases = (
            ([64], [128], {}, CAUSAL),
            ([64], [256], {0: [(20, 100)]}, CAUSAL),
            ([64], [128], {0: [(20, 100)]}, GENERAL),
            ([64, 7], [128, 256], {1: [(250, 260)]}, GENERAL),
            ([64, 7], [128, 256], {1: [(20, 100)]}, CAUSAL),
            ([64], [128], {0: [(128, 150)]}, CAUSAL),
        )
        for lengths, ends, ranges, expected in cases:
            with self.subTest(lengths=lengths, ends=ends, ranges=ranges):
                self.assertEqual(policy.select(metadata(lengths, ends, ranges)), expected)

    def test_unclamped_image_boundary_retains_the_general_kernel(self):
        value = metadata([16], [32], {0: [(10, 16)]})
        self.assertEqual(routing(6, clamped=True).select(value), CAUSAL)
        self.assertEqual(routing(6, clamped=False).select(value), GENERAL)


if __name__ == "__main__":
    unittest.main()
