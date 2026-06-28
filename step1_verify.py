# -*- coding: utf-8 -*-
import os
import sys
import requests
from dotenv import load_dotenv
import progress

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv("input/.env")

print("=" * 50)
print("[1단계] 환경 검증 및 텔레그램 연결 테스트")
print("=" * 50)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

errors = []
for name, val in [
    ("TELEGRAM_BOT_TOKEN", TELEGRAM_TOKEN),
    ("TELEGRAM_CHAT_ID", CHAT_ID),
    ("GOOGLE_SHEET_ID", GOOGLE_SHEET_ID),
    ("GOOGLE_APPLICATION_CREDENTIALS", GOOGLE_CREDS),
]:
    if val:
        masked = val[:6] + "..." + val[-4:] if len(val) > 10 else "***"
        print(f"  [OK] {name} = {masked}")
    else:
        print(f"  [FAIL] {name} 누락!")
        errors.append(name)

if errors:
    print(f"\n오류: 다음 변수가 .env에 없습니다: {errors}")
    sys.exit(1)

print("\n모든 환경변수 정상 로드 완료.")

url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
msg = "아침 브리핑 시스템 구축 1단계 성공 (테스트 메시지)"
resp = requests.post(url, json={"chat_id": CHAT_ID, "text": msg})

if resp.status_code == 200:
    print(f"텔레그램 발송 성공: {msg}")
else:
    print(f"텔레그램 발송 실패: {resp.text}")
    sys.exit(1)

progress.save(1, "1단계 완료")
print("\n1단계 완료!")
