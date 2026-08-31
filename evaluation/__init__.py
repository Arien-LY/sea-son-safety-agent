"""Deterministic Phase 6 evaluation helpers; never call a model or network."""

from evaluation.scoring import build_report, load_run, render_report

__all__ = ["build_report", "load_run", "render_report"]
