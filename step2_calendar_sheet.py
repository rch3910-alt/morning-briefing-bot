# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import progress

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv("input/.env")

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDS_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

print("=" * 50)
print("[2단계] 구글 캘린더 & 시트 중복 방지 연동")
print("=" * 50)

creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)

# --- 구글 시트 중복 방지 체크 ---
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)
worksheet = sh.sheet1

today_str = datetime.now().strftime("%Y-%m-%d")
existing = worksheet.col_values(1)

if today_str in existing:
    print(f"[중복 방지] 오늘({today_str}) 이미 알림 발송됨. 스킵.")
    already_sent = True
else:
    print(f"[중복 방지] 오늘({today_str}) 발송 기록 없음. 계속 진행.")
    already_sent = False

# --- 구글 캘린더 오늘 일정 조회 ---
def get_today_events():
    service = build("calendar", "v3", credentials=creds)
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

    result = service.events().list(
        calendarId="primary",
        timeMin=day_start,
        timeMax=day_end,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])

events = get_today_events()

if events:
    print(f"\n오늘 캘린더 일정 ({len(events)}개):")
    for e in events[:3]:
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        print(f"  - [{start}] {e.get('summary', '(제목 없음)')}")
else:
    print("\n오늘 캘린더 일정 없음.")

progress.save(2, "2단계 완료")
print("\n2단계 완료!")
print("(실제 알림 발송 시 시트에 날짜 기록은 main.py에서 처리됩니다)")
