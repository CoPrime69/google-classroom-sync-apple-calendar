"""Tests for grade arithmetic.

The calculator is pure, so these are real tests of the rules rather than
smoke tests of wiring. Each case below corresponds to a rule in
docs/superpowers/specs/2026-08-07-grade-tracker-design.md.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from src.grades.calculator import Component, Group, evaluate_course, evaluate_group


def quiz(name, score, out_of=10):
    return Component(key=name, name=name, score=score, max_score=out_of)


def group(name="Quizzes", weight=15.0, counted=5, components=()):
    return Group(
        key=name, name=name, weight=weight, counted=counted,
        components=tuple(components),
    )


# ---------------------------------------------------------------- surplus rule


def test_nothing_dropped_below_keep_count():
    """Two of five quizzes graded: both count, each worth weight/keep."""
    result = evaluate_group(group(components=[quiz("Q1", 8), quiz("Q2", 5)]))

    assert [c.name for c in result.components if c.is_counted] == ["Q1", "Q2"]
    # 15/5 = 3 each, not 15/2 = 7.5. Dividing by the graded count would
    # inflate early components and rewrite itself later.
    assert result.graded_weight == pytest.approx(6.0)
    assert result.earned_weight == pytest.approx(0.8 * 3 + 0.5 * 3)


def test_exactly_keep_count_drops_nothing():
    comps = [quiz(f"Q{i}", 8) for i in range(1, 6)]
    result = evaluate_group(group(components=comps))

    assert sum(1 for c in result.components if c.is_counted) == 5
    assert result.graded_weight == pytest.approx(15.0)


def test_cv_six_quizzes_drops_one():
    """CV: 'n-1 if six quizzes' falls out of counted=5 with no edit."""
    comps = [quiz("Q1", 8), quiz("Q2", 5), quiz("Q3", 9),
             quiz("Q4", 7), quiz("Q5", 6), quiz("Q6", 4)]
    result = evaluate_group(group(components=comps))

    dropped = [c.name for c in result.components if not c.is_counted]
    assert dropped == ["Q6"]
    assert result.graded_weight == pytest.approx(15.0)


def test_cv_seven_quizzes_drops_two():
    """CV: 'n-2 if seven quizzes' -- same counted=5, still no edit."""
    comps = [quiz("Q1", 8), quiz("Q2", 5), quiz("Q3", 9), quiz("Q4", 7),
             quiz("Q5", 6), quiz("Q6", 4), quiz("Q7", 3)]
    result = evaluate_group(group(components=comps))

    dropped = sorted(c.name for c in result.components if not c.is_counted)
    assert dropped == ["Q6", "Q7"]
    # Each survivor is still worth 3%; the group never exceeds its weight.
    assert result.graded_weight == pytest.approx(15.0)


# ------------------------------------------------------------------- ranking


def test_ranks_by_fraction_not_raw_score():
    """6/20 (30%) is worse than 5/10 (50%) despite being the bigger number."""
    comps = [
        quiz("Q1", 17, 20), quiz("Q2", 5, 10), quiz("Q3", 8, 10),
        quiz("Q4", 7, 10), quiz("Q5", 15, 20), quiz("Q6", 6, 20),
    ]
    result = evaluate_group(group(components=comps))

    dropped = [c.name for c in result.components if not c.is_counted]
    assert dropped == ["Q6"], "ranking by raw score would wrongly drop Q2"


def test_tie_break_is_stable():
    """Equal scores must drop the same component however the rows are ordered.

    Compares the set of survivors, not their order: results preserve input
    order, so a reversed input legitimately lists the same survivors
    differently.
    """
    comps = [quiz("Qb", 5), quiz("Qa", 5), quiz("Qc", 5)]
    first = evaluate_group(group(counted=2, components=comps))
    second = evaluate_group(group(counted=2, components=list(reversed(comps))))

    assert ({c.name for c in first.components if c.is_counted}
            == {c.name for c in second.components if c.is_counted}
            == {"Qa", "Qb"})


# ------------------------------------------------------------------- ungraded


def test_ungraded_excluded_from_both_sides():
    """A row with no score must not drag the average down."""
    result = evaluate_group(group(components=[quiz("Q1", 8), quiz("Q2", None)]))

    counted = [c.name for c in result.components if c.is_counted]
    assert counted == ["Q1"]
    assert result.graded_weight == pytest.approx(3.0)
    assert result.earned_weight == pytest.approx(2.4)


def test_zero_graded_reports_not_graded():
    course = evaluate_course("CSL7360", [group(components=[quiz("Q1", None)])])

    assert course.is_graded is False
    assert course.percentage is None
    assert course.marks == "not graded yet"


# ---------------------------------------------------------------- counted=None


def test_counted_none_splits_across_rows_present():
    """EVS 'Class Assignments, as needed': weight re-splits as rows appear."""
    two = evaluate_group(group("Class Assignments", 10.0, None,
                               [quiz("A1", 8), quiz("A2", 6)]))
    assert two.keep == 2
    assert two.graded_weight == pytest.approx(10.0)

    three = evaluate_group(group("Class Assignments", 10.0, None,
                                 [quiz("A1", 8), quiz("A2", 6), quiz("A3", 7)]))
    assert three.keep == 3
    # Still 10% total; each row is now worth 3.33 rather than 5.
    assert three.graded_weight == pytest.approx(10.0)
    assert three.components[0].effective_weight == pytest.approx(10 / 3)


def test_counted_none_drops_nothing():
    g = group("Class Assignments", 10.0, None, [quiz("A1", 1), quiz("A2", 10)])
    result = evaluate_group(g)
    assert all(c.is_counted for c in result.components)


# --------------------------------------------------------------------- guards


def test_counted_below_one_clamps():
    result = evaluate_group(group(counted=0, components=[quiz("Q1", 8)]))
    assert result.keep == 1
    assert any("treating as 1" in w for w in result.warnings)


def test_zero_max_is_skipped():
    result = evaluate_group(group(components=[quiz("Q1", 8), quiz("Q2", 5, 0)]))
    assert [c.name for c in result.components if c.is_counted] == ["Q1"]
    assert any("max score" in w for w in result.warnings)


def test_negative_score_rejected():
    result = evaluate_group(group(components=[quiz("Q1", -3)]))
    assert not any(c.is_counted for c in result.components)
    assert any("negative" in w for w in result.warnings)


def test_bonus_marks_allowed_but_flagged():
    result = evaluate_group(group(counted=1, components=[quiz("Q1", 12, 10)]))
    assert result.earned_weight == pytest.approx(1.2 * 15.0)
    assert any("exceeds max" in w for w in result.warnings)


def test_weights_not_summing_to_100_warns_but_computes():
    course = evaluate_course("X", [
        group("Minor", 20.0, 1, [quiz("M", 8)]),
        group("Major", 50.0, 1, [quiz("J", 9)]),
    ])
    assert any("70" in w for w in course.warnings)
    assert course.is_graded


# ------------------------------------------------- real published policies


def test_cv_policy_end_to_end():
    """CSL7360 as published: 10/15/15/20/40, quizzes best-5 of seven."""
    course = evaluate_course("CSL7360", [
        group("Assignments", 10.0, 2, [quiz("A1", 8), quiz("A2", 9)]),
        group("Quizzes", 15.0, 5, [
            quiz("Q1", 8), quiz("Q2", 5), quiz("Q3", 17, 20),
            quiz("Q4", 7), quiz("Q5", 6, 20), quiz("Q6", 15, 20),
        ]),
        group("Mini Project", 15.0, 1, []),
        group("Minor", 20.0, 1, []),
        group("Major", 40.0, 1, []),
    ])

    assert course.warnings == ()          # sums to exactly 100
    # Only assignments and quizzes are graded: 10 + 15 of weight.
    assert course.graded_weight == pytest.approx(25.0)
    assert 0 < course.percentage < 100


def test_evs_policy_with_open_ended_group():
    """CIL4010: 20/50/10/10/10, Class Assignments open-ended."""
    course = evaluate_course("CIL4010", [
        group("Minor", 20.0, 1, [quiz("Minor", 15, 20)]),
        group("Major", 50.0, 1, []),
        group("Class Assignments", 10.0, None, [quiz("CA1", 9), quiz("CA2", 7)]),
        group("PPT presentation", 10.0, 1, []),
        group("Video presentation", 10.0, 1, []),
    ])

    assert course.warnings == ()
    assert course.graded_weight == pytest.approx(30.0)


def test_ibm_policy_all_single_component():
    """MSL4010: no quizzes at all, every group a single item."""
    course = evaluate_course("MSL4010", [
        group("Participation", 10.0, 1, [quiz("Attendance", 9)]),
        group("Group Project", 15.0, 1, []),
        group("Minor", 25.0, 1, []),
        group("Major", 50.0, 1, []),
    ])

    assert course.warnings == ()
    assert course.marks == "9.00 / 10.00"


def test_course_with_no_groups_is_not_an_error():
    """A course added to Notion before its policy is filled in."""
    course = evaluate_course("NEW101", [])
    assert course.warnings == ()
    assert course.marks == "not graded yet"


# --------------------------------------------------- gaps found in review


def test_score_of_exactly_zero_counts():
    """0 is a real mark. The counterpart of the None-is-not-zero rule."""
    result = evaluate_group(group(components=[quiz("Q1", 0), quiz("Q2", 8)]))

    assert all(c.is_counted for c in result.components)
    assert result.graded_weight == pytest.approx(6.0)   # both consume weight
    assert result.earned_weight == pytest.approx(2.4)   # only Q2 earns


def test_zero_ranks_last_and_is_dropped_first():
    comps = [quiz("Q1", 0), quiz("Q2", 8), quiz("Q3", 7)]
    result = evaluate_group(group(counted=2, components=comps))
    assert [c.name for c in result.components if not c.is_counted] == ["Q1"]


def test_rollup_excludes_dropped_and_ungraded():
    """The string written to Notion; previously untested."""
    comps = [
        quiz("Q3", 17, 20), quiz("Q1", 8), quiz("Q6", 15, 20),
        quiz("Q4", 7), quiz("Q2", 5), quiz("Q5", 6, 20),
        quiz("Q7", None),
    ]
    result = evaluate_group(group(counted=5, components=comps))
    assert result.rollup == "52/70"


def test_surplus_and_ungraded_together():
    """Both rules firing at once -- the common mid-semester shape."""
    comps = [quiz(f"Q{i}", 8) for i in range(1, 7)] + [quiz("Q7", None)]
    result = evaluate_group(group(counted=5, components=comps))

    counted = [c for c in result.components if c.is_counted]
    assert len(counted) == 5
    assert result.graded_weight == pytest.approx(15.0)
    assert result.components[-1].is_counted is False   # ungraded one


def test_duplicate_component_keys_do_not_leak_weight():
    """Survivors are tracked by position, so a repeated key is harmless.

    Production keys are Notion page ids and unique, but nothing enforces it
    and a collision used to make an ungraded row inherit a survivor's weight.
    """
    comps = (Component(key="dup", name="Q1", score=8, max_score=10),
             Component(key="dup", name="Q1 again", score=None, max_score=10))
    result = evaluate_group(Group(key="g", name="Quizzes", weight=15.0,
                                  counted=5, components=comps))

    assert [c.is_counted for c in result.components] == [True, False]
    assert result.graded_weight == pytest.approx(3.0)
    assert result.rollup == "8/10"


def test_counted_none_with_no_rows():
    result = evaluate_group(group("Class Assignments", 10.0, None, []))
    assert result.graded_weight == pytest.approx(0.0)
    assert result.rollup == "0/0"


def test_negative_weight_is_flagged():
    """Two groups cancelling to zero would otherwise report 'not graded'."""
    course = evaluate_course("X", [
        group("Good", 50.0, 1, [quiz("A", 8)]),
        group("Bad", -50.0, 1, [quiz("B", 8)]),
    ])
    assert any("negative weight" in w for w in course.warnings)


def test_duplicate_group_warning_shows_typed_name():
    course = evaluate_course("X", [
        group("Quizzes", 50.0, 1, []),
        Group(key="g2", name="Quizzes", weight=50.0, counted=1, components=()),
    ])
    assert any("'Quizzes'" in w for w in course.warnings)
