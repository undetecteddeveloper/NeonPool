"""AC7: tools/netbench.py prints its numbers and says which are simulated, which not measured."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_bench():
    spec = importlib.util.spec_from_file_location("netbench", ROOT / "tools" / "netbench.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ac7_netbench_reports_both_labels(capsys):
    bench = load_bench()
    assert bench.main(["--quick"]) == 0
    out = capsys.readouterr().out
    assert "giả lập (đã đo)" in out
    assert "hai máy thật: CHƯA ĐO" in out
    for part in ("p50", "p95", "p99", "phần game", "Cơ đối thủ", "Điểm kiểm"):
        assert part in out


def test_netbench_percentiles_and_the_cue_budget():
    bench = load_bench()
    assert bench.percentile([1, 2, 3, 4, 5], 50) == 3
    assert bench.percentile([5, 1], 99) == 5
    cue = bench.cue_bandwidth(2.0)
    assert cue["packets_per_s"] == 30
    assert cue["app_bytes_per_s"] < 2048 and cue["wire_bytes_per_s"] < 2048


def test_the_game_s_own_share_of_a_shot_is_far_below_the_budget():
    bench = load_bench()
    r = bench.one_way(20, 2, 0.0, 300, seed=1)
    assert bench.percentile(r["game"], 95) < bench.LIMIT_GAME_MS
