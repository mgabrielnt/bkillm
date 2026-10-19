"""Quality measurement (`golden`, `eval` commands). Every run costs API credits.

  golden.py          draft the golden test set from random chunks + hand-written unanswerable questions
  retrieval_eval.py  hit@k / MRR: is the right document retrieved for each question?
  judge.py           LLM judge: correctness, faithfulness, citations, refusals
  runner.py          run the configurations and write the summary files
"""
