"""AC8 / invariant 5: every word on screen is translated, in both languages."""

import re
from pathlib import Path

import pytest

from game import i18n
from game.config import FEEL_SETS

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "game"
T_CALL = re.compile(r"""\bt\(\s*["']([\w.]+)["']""")
VIETNAMESE = re.compile(
    "[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]"
)


@pytest.fixture(autouse=True)
def reset_lang():
    yield
    i18n.set_lang("vi")


def test_both_languages_have_exactly_the_same_keys():
    vi, en = i18n.table("vi"), i18n.table("en")
    assert set(vi) == set(en), set(vi) ^ set(en)


def test_no_empty_strings():
    for lang in i18n.LANGS:
        assert all(v.strip() for v in i18n.table(lang).values()), lang


def test_every_t_call_in_the_code_has_a_key():
    missing = []
    for path in GAME.rglob("*.py"):
        if path.name == "i18n.py":  # defines t(); its docstring shows an example call
            continue
        for key in T_CALL.findall(path.read_text(encoding="utf-8")):
            if key not in i18n.table("vi"):
                missing.append(f"{path.relative_to(ROOT)}: {key}")
    assert missing == []


def test_every_feel_set_name_key_is_translated():
    for fs in FEEL_SETS.values():
        assert fs.name_key in i18n.table("vi") and fs.name_key in i18n.table("en")


def test_no_hard_coded_vietnamese_in_code():
    offenders = [
        str(p.relative_to(ROOT))
        for p in GAME.rglob("*.py")
        if VIETNAMESE.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_switching_language_changes_text_and_falls_back_to_the_key():
    i18n.set_lang("vi")
    vi = i18n.t("menu.play")
    i18n.set_lang("en")
    assert i18n.t("menu.play") != vi
    assert i18n.t("no.such.key") == "no.such.key"


def test_an_unknown_language_is_rejected():
    i18n.set_lang("vi")
    with pytest.raises(ValueError):
        i18n.set_lang("fr")


def test_keys_built_at_run_time_exist():
    """t(f"group.{g}") and the rules' foul/result keys cannot be found by the literal-call scan."""
    dynamic = [
        "group.open",
        "group.solid",
        "group.stripe",
        "notice.group_solid",
        "notice.group_stripe",
    ]
    dynamic += ["foul.scratch", "foul.no_hit", "foul.wrong_ball", "foul.no_cushion"]
    dynamic += ["result.lost_early", "result.lost_foul", "result.won", "result.lost"]
    for lang in i18n.LANGS:
        assert set(dynamic) <= set(i18n.table(lang)), lang


def test_format_arguments():
    i18n.table("vi")["_test"] = "Còn {n} bi"
    try:
        assert i18n.t("_test", n=3) == "Còn 3 bi"
    finally:
        del i18n.table("vi")["_test"]
