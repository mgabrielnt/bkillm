"""Quality measurement (`golden`, `eval` commands).

  catalog/           metrics definitions (Stage 1 retrieval, Stage 2 answers)
  retrieval_eval.py  Stage 1: Hit@10, MRR@10 (cheap)
  judge.py           Stage 2: LLM judge for faithfulness, correctness, refusals; latency & cost
  golden.py          golden test set generation
  guard.py           keeps the run alive when the API fails (errors recorded per question)
  report.py          prints the metrics table and saves the summary file
  runner.py          orchestrator: retrieval, answers, judge, results
"""
from .catalog import ANSWERS, RETRIEVAL, STAGES
from .golden import build_golden, load_golden
from .judge import judge, summarize
from .retrieval_eval import evaluate_retrieval
from .runner import run

__all__ = [
    "STAGES",
    "RETRIEVAL",
    "ANSWERS",
    "evaluate_retrieval",
    "judge",
    "summarize",
    "build_golden",
    "load_golden",
    "run",
]
