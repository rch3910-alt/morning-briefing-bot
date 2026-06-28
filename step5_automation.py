# -*- coding: utf-8 -*-
import sys
import os
import progress

sys.stdout.reconfigure(encoding="utf-8")

print("=" * 50)
print("[5단계] 자동화 파일 생성 완료 확인")
print("=" * 50)

files = [
    ("output/run.bat", "윈도우 배치 실행 파일"),
    (".github/workflows/morning_briefing.yml", "GitHub Actions 워크플로우"),
    ("requirements.txt", "Python 패키지 목록"),
    ("main.py", "메인 실행 스크립트"),
]

all_ok = True
for path, desc in files:
    if os.path.exists(path):
        print(f"  [OK] {path}  ({desc})")
    else:
        print(f"  [MISS] {path}  ({desc})")
        all_ok = False

print()
print("[ GitHub Actions 크론 설정 ]")
print("  크론: '30 21 * * *'")
print("  의미: 매일 UTC 21:30 = 한국 시간 06:30")
print()
print("[ GitHub Secrets 등록 필요 항목 ]")
print("  TELEGRAM_BOT_TOKEN        — 텔레그램 봇 토큰")
print("  TELEGRAM_CHAT_ID          — 텔레그램 채팅 ID")
print("  GOOGLE_SHEET_ID           — 구글 시트 ID")
print("  GOOGLE_APPLICATION_CREDENTIALS — service-account.json 파일 내용 전체")

if all_ok:
    progress.save(5, "5단계 완료")
    print("\n5단계 완료!")
else:
    print("\n[주의] 일부 파일 누락.")
