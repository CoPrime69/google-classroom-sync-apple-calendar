"""
Grade arithmetic.

Pure functions with no I/O. Everything the calculator needs arrives as
arguments, so the rules below can be tested directly without Notion or
Supabase.

Nothing here knows about specific courses, categories or semesters. A group is
just a name, a weight and a count; a course is just a code and some groups. The
same code handles a course with two groups and one with eight, this semester or
any later one.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Component:
    """One graded item: a quiz, an assignment, a presentation."""

    key: str
    name: str
    score: Optional[float] = None
    max_score: Optional[float] = None

    @property
    def is_graded(self) -> bool:
        """A component counts only once it has a score.

        A score of None means "not marked yet", which is different from zero.
        Treating it as zero would report a falsely low standing all term.
        """
        return self.score is not None


@dataclass(frozen=True)
class Group:
    """A weighted category of components, e.g. Quizzes at 15%.

    `counted` is how many components contribute to the grade:
      - a number  -> best N of however many exist (CV: "5-7 quizzes" is best 5)
      - None      -> all of them count, weight split across the rows present
    """

    key: str
    name: str
    weight: float
    counted: Optional[int] = None
    components: Tuple[Component, ...] = ()


@dataclass(frozen=True)
class ComponentResult:
    key: str
    name: str
    score: Optional[float]
    max_score: Optional[float]
    fraction: Optional[float]
    is_counted: bool
    effective_weight: float
    earned: float


@dataclass(frozen=True)
class GroupResult:
    key: str
    name: str
    weight: float
    keep: int
    earned_weight: float
    graded_weight: float
    raw_scored: float
    raw_total: float
    components: Tuple[ComponentResult, ...]
    warnings: Tuple[str, ...] = ()

    @property
    def rollup(self) -> str:
        """Raw marks over raw available, counting only surviving components."""
        return f"{_trim(self.raw_scored)}/{_trim(self.raw_total)}"


@dataclass(frozen=True)
class CourseResult:
    course: str
    earned_weight: float
    graded_weight: float
    groups: Tuple[GroupResult, ...]
    warnings: Tuple[str, ...] = ()

    @property
    def is_graded(self) -> bool:
        return self.graded_weight > 0

    @property
    def percentage(self) -> Optional[float]:
        if not self.is_graded:
            return None
        return self.earned_weight / self.graded_weight * 100.0

    @property
    def marks(self) -> str:
        """The Summary-page figure: earned out of weight graded so far.

        Deliberately a fraction rather than a percent of 100. Early in a term
        "3.2/100" reads as a catastrophe when it only means little has been
        graded; "3.2/4.0" reads correctly.
        """
        if not self.is_graded:
            return "not graded yet"
        return f"{self.earned_weight:.2f} / {self.graded_weight:.2f}"


def _trim(value: float) -> str:
    """Render 32.0 as '32' but 32.5 as '32.5'."""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def evaluate_group(group: Group) -> GroupResult:
    """Compute one group's contribution.

    Components are ranked by score/max, not raw score. With mixed maximums in
    a group, raw ordering drops the wrong one: 6/20 (30%) is a worse
    performance than 5/10 (50%) despite being the higher number.
    """
    warnings: List[str] = []

    # Survivors are tracked by position, not by Component.key. Keys are Notion
    # page ids in practice and so unique, but nothing enforced that, and a
    # duplicate key made an unrelated component inherit a survivor's weight.
    usable: List[int] = []

    for index, component in enumerate(group.components):
        if not component.is_graded:
            continue
        if component.max_score is None or component.max_score <= 0:
            warnings.append(
                f"{component.name}: max score is {component.max_score!r}, skipped"
            )
            continue
        if component.score < 0:
            warnings.append(f"{component.name}: negative score, skipped")
            continue
        if component.score > component.max_score:
            warnings.append(
                f"{component.name}: score {_trim(component.score)} exceeds max "
                f"{_trim(component.max_score)}, counted as-is"
            )
        usable.append(index)

    keep, keep_warning = _keep_count(group)
    if keep_warning:
        warnings.append(keep_warning)

    def fraction_of(index: int) -> float:
        component = group.components[index]
        return component.score / component.max_score

    # Name then index break ties, so a rerun on unchanged data never silently
    # swaps which component was dropped.
    ranked = sorted(
        usable,
        key=lambda i: (-fraction_of(i), group.components[i].name, i),
    )

    # Only drop once there is a surplus. While the number graded is at or
    # below the keep count every one of them counts; the drop starts with the
    # next. Slicing already clamps, so no min() is needed.
    survivors = set(ranked[:keep])

    weight_per_survivor = group.weight / keep

    results: List[ComponentResult] = []
    earned_weight = 0.0
    graded_weight = 0.0
    raw_scored = 0.0
    raw_total = 0.0

    for index, component in enumerate(group.components):
        counted = index in survivors
        fraction = fraction_of(index) if index in usable else None
        earned = 0.0
        effective = 0.0

        if counted:
            # Guaranteed graded with a positive max: only indices in `usable`
            # can reach here, so no fallbacks are needed.
            effective = weight_per_survivor
            earned = fraction * weight_per_survivor
            earned_weight += earned
            graded_weight += weight_per_survivor
            raw_scored += component.score
            raw_total += component.max_score

        results.append(
            ComponentResult(
                key=component.key,
                name=component.name,
                score=component.score,
                max_score=component.max_score,
                fraction=fraction,
                is_counted=counted,
                effective_weight=effective,
                earned=earned,
            )
        )

    return GroupResult(
        key=group.key,
        name=group.name,
        weight=group.weight,
        keep=keep,
        earned_weight=earned_weight,
        graded_weight=graded_weight,
        raw_scored=raw_scored,
        raw_total=raw_total,
        components=tuple(results),
        warnings=tuple(warnings),
    )


def _keep_count(group: Group) -> Tuple[int, Optional[str]]:
    """How many components in this group contribute, plus any warning.

    None means every row present counts, which is how a category with an
    open-ended number of items and no drops is expressed. The weight then
    re-splits automatically as rows are added.

    Returns a warning rather than appending to a caller's list, so this module
    keeps no side effects.
    """
    if group.counted is None:
        return max(1, len(group.components)), None

    if group.counted < 1:
        return 1, f"{group.name}: counted is {group.counted}, treating as 1"

    return group.counted, None


def evaluate_course(course: str, groups: Sequence[Group]) -> CourseResult:
    """Combine group results into one standing for a course."""
    group_results = [evaluate_group(g) for g in groups]

    earned = sum(g.earned_weight for g in group_results)
    graded = sum(g.graded_weight for g in group_results)

    warnings: List[str] = []

    for group in groups:
        # The only numeric field without its own guard. A negative weight can
        # cancel a positive one so graded_weight lands on zero, making a course
        # with real marks report "not graded yet".
        if group.weight < 0:
            warnings.append(f"{group.name}: negative weight {_trim(group.weight)}")

    total_weight = sum(g.weight for g in groups)
    if groups and abs(total_weight - 100.0) > 0.01:
        # Warn rather than reject or normalise. Rejecting is obnoxious while
        # groups are still being entered mid-term; normalising would hide a
        # genuine data-entry mistake behind a plausible-looking number.
        warnings.append(f"weights sum to {_trim(total_weight)}%, not 100%")

    seen: Dict[str, List[str]] = {}
    for g in groups:
        seen.setdefault(g.name.strip().lower(), []).append(g.name)
    for names in seen.values():
        if len(names) > 1:
            # Report the name as typed, not the normalised key.
            warnings.append(f"{len(names)} groups named {names[0]!r}")

    return CourseResult(
        course=course,
        earned_weight=earned,
        graded_weight=graded,
        groups=tuple(group_results),
        warnings=tuple(warnings),
    )
