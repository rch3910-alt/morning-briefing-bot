# -*- coding: utf-8 -*-
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

PROGRESS_FILE = "progress_save.json"

INDICATORS = {
    0: "[][][][] [][]  0%",
    1: "[#][][][] []  16%",
    2: "[#][#][][] []  33%",
    3: "[#][#][#][]  50%",
    4: "[#][#][#][#]  66%",
    5: "[#][#][#][#][#]  83%",
    6: "[#][#][#][#][#][#] 100%",
}

BARS = {
    0: "□□□□□□  0%",
    1: "■□□□□□ 16%",
    2: "■■□□□□ 33%",
    3: "■■■□□□ 50%",
    4: "■■■■□□ 66%",
    5: "■■■■■□ 83%",
    6: "■■■■■■ 100%",
}

def load():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"total_steps": 6, "current_step": 0, "completed_steps": [], "status": "시작 전", "last_updated": ""}

def save(step, status="진행 중"):
    data = load()
    data["current_step"] = step
    data["status"] = status
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if step > 0 and step not in data["completed_steps"]:
        data["completed_steps"].append(step)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        print(f"[진행 인디케이터: {BARS[step]} 완료]")
    except UnicodeEncodeError:
        print(f"[진행 인디케이터: {INDICATORS[step]} 완료]")
    return data
