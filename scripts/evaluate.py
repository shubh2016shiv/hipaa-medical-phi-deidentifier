import json
from collections import defaultdict
from typing import List, Dict, Tuple

def iou(a: Tuple[int,int], b: Tuple[int,int]) -> float:
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter/union if union else 0.0

def prf(gold: List[Dict], pred: List[Dict], iou_thr=0.2):
    tp=0; fp=0; fn=0
    matched=[False]*len(gold)
    for p in pred:
        ps=(p["start"], p["end"])
        label=p["label"]
        hit=False
        for i,g in enumerate(gold):
            if matched[i] or g["label"]!=label: continue
            if iou(ps,(g["start"],g["end"]))>=iou_thr:
                matched[i]=True; hit=True; break
        tp += 1 if hit else 0
        fp += 0 if hit else 1
    fn = matched.count(False)
    prec = tp/(tp+fp) if tp+fp else 0.0
    rec  = tp/(tp+fn) if tp+fn else 0.0
    f1   = 2*prec*rec/(prec+rec) if prec+rec else 0.0
    return prec, rec, f1
