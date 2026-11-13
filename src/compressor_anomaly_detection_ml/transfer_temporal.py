"""Causal context from completed provider cycles, without using their labels."""

import numpy as np

from .domain import DataValidationError


def cycle_context(frame, *, history_size=10, minimum_history=3, maximum_gap_hours=12):
    if "partition_name" in frame and frame.partition_name.eq("test").any():
        raise DataValidationError("Reserved test cycles cannot enter development context.")
    return completed_cycle_context(
        frame,
        history_size=history_size,
        minimum_history=minimum_history,
        maximum_gap_hours=maximum_gap_hours,
    )


def completed_cycle_context(frame, *, history_size=10, minimum_history=3, maximum_gap_hours=12):
    """Pure causal calculation; partition authorization belongs to its caller."""
    if not 1 <= minimum_history <= history_size or maximum_gap_hours <= 0:
        raise DataValidationError("Cycle history limits must be positive and consistent.")
    if not frame.index.is_unique or frame.observation_id.duplicated().any():
        raise DataValidationError("Cycle identities and row indices must be unique.")
    result = frame.copy()
    duration = (result.ended_at - result.started_at).dt.total_seconds()
    if (
        result.dependency_group_id.isna().any()
        or not np.isfinite(duration).all()
        or duration.le(0).any()
    ):
        raise DataValidationError("Completed cycles require positive duration and explicit groups.")
    result["elapsed_seconds"] = duration
    result["duration_relative_history"] = np.nan
    result["history_cycles_support"] = 0
    result["observed_context_gap_seconds"] = np.nan
    for _, group in result.groupby("dependency_group_id", sort=True):
        history, previous_end = [], None
        for index, row in group.sort_values(["started_at", "observation_id"]).iterrows():
            gap = None if previous_end is None else (row.started_at - previous_end).total_seconds()
            if gap is not None and (gap < 0 or gap > maximum_gap_hours * 3600):
                history = []
            result.loc[index, "history_cycles_support"] = len(history)
            if gap is not None:
                result.loc[index, "observed_context_gap_seconds"] = gap
            if len(history) >= minimum_history:
                result.loc[index, "duration_relative_history"] = row.elapsed_seconds / float(
                    np.median(history)
                )
            history = [*history, row.elapsed_seconds][-history_size:]
            previous_end = row.ended_at
    return result
