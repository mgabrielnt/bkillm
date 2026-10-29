"""Definitions of every evaluation metric (name, purpose, target), one module per stage.

  retrieval.py  Stage 1 - document retrieval (Hit@10, MRR@10)
  answers.py    Stage 2 - faithfulness, correctness, negative rejection, false refusal
"""
from .answers import ANSWERS
from .retrieval import RETRIEVAL

STAGES = {"retrieval": RETRIEVAL, "answers": ANSWERS}

__all__ = ["STAGES", "RETRIEVAL", "ANSWERS"]
