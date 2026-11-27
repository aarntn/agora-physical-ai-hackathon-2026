from nasocheck import protocol
from nasocheck.contracts import TrialIn
from nasocheck.scoring import rejection_reasons, score_db
from nasocheck.speech import spoken_db


def trial(**kw):
    base = dict(trial_id="t1", session_id="s1", type="oral", start_ms=0, end_ms=2000,
                ratio_db=-18.0, spread_db=1.0, voiced_frames=40, mic_clipped=False,
                accel_snr_db=14.0, imu_hz=1594)
    base.update(kw)
    return TrialIn(**base)


def test_good_trial_has_no_reasons():
    assert rejection_reasons(trial()) == []


def test_each_rule():
    assert rejection_reasons(trial(mic_clipped=True)) == ["clipped"]
    assert rejection_reasons(trial(voiced_frames=10)) == ["too_short"]
    assert rejection_reasons(trial(accel_snr_db=3)) == ["weak_vibration"]
    assert rejection_reasons(trial(spread_db=5)) == ["unstable"]
    assert rejection_reasons(trial(imu_hz=800)) == ["sensor_rate"]
    assert "no_ratio" in rejection_reasons(trial(ratio_db=None))


def test_control_tolerates_low_snr():
    assert rejection_reasons(trial(type="control", accel_snr_db=1, voiced_frames=3)) == []


def test_score_is_relative_to_hum():
    assert score_db(-18.0, -2.0) == -16.0


def test_phrase_matching():
    assert protocol.phrase_matches("Papa pakai topi.", "Papa pakai topi")
    assert protocol.phrase_matches("um papa pakai topi okay", "Papa pakai topi")
    assert protocol.phrase_matches("papa pakay topi", "Papa pakai topi")      # ASR slip
    assert not protocol.phrase_matches("kakak beli kuih", "Papa pakai topi")
    assert not protocol.phrase_matches("", "Papa pakai topi")


def test_oral_phrases_have_no_nasal_consonants():
    for lang, phrases in protocol.PHRASES.items():
        for p in phrases:
            assert not set("mn") & set(p.lower()), (lang, p)


def test_steps_and_messages_both_languages():
    for lang in ("en", "ms"):
        steps = protocol.steps_for(lang, 2)
        assert [s.type for s in steps] == ["hum", "oral", "nasal", "oral", "nasal"]
        for code in protocol.REASONS:
            assert protocol.reason_text(code, lang, "x")
        assert protocol.instruction(None, lang)


def test_spoken_db():
    assert spoken_db(-18.44, "en") == "minus 18.4 decibels"
    assert spoken_db(-0.01, "en") == "0.0 decibels"
    assert spoken_db(3.0, "ms") == "3 perpuluhan 0 desibel"
