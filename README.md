# 아침 브리핑 봇

매일 아침 미국 증시 마감 후 날씨·뉴스·미세먼지를 텔레그램으로 자동 발송하는 봇입니다.

## 발송 내용

- **미국 증시**: 나스닥·금·비트코인 종가 및 등락
- **공포&탐욕 지수**: CNN Fear & Greed Index
- **미증시 뉴스 TOP5**: Bloomberg·WSJ·CNBC RSS (한국어 자동 번역)
- **반도체 뉴스 TOP5**: Bloomberg Tech·CNBC Tech·EE Times (한국어 자동 번역)
- **오늘 일정**: Google 캘린더 연동
- **날씨**: 기상청 단기예보 — 기온·강수확률·강수시간대
- **미세먼지**: 에어코리아 실측 관측소 데이터

**발송 시각**: 매일 KST 05:10 (미국 증시 마감 후)

---

## 사전 준비

아래 계정과 API 키가 필요합니다.

| 항목 | 발급처 |
|------|--------|
| 텔레그램 봇 토큰 + 채팅 ID | Telegram @BotFather |
| Google 서비스 계정 JSON | Google Cloud Console |
| Google 시트 ID | Google Sheets |
| Google 캘린더 ID | Google Calendar |
| 기상청 API 키 | 공공데이터포털 (data.go.kr) |
| 에어코리아 API 키 | 공공데이터포털 (data.go.kr) |

---

## 설정 단계

### 1. 텔레그램 봇 만들기

1. 텔레그램에서 `@BotFather` 검색 → `/newbot` 명령
2. 봇 이름 입력 → **Bot Token** 발급
3. 발급된 봇에 메시지 한 번 전송
4. 아래 URL에서 `chat_id` 확인:
   ```
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   ```

---

### 2. Google Cloud 설정

#### 서비스 계정 생성
1. [console.cloud.google.com](https://console.cloud.google.com) → 새 프로젝트 생성
2. **API 및 서비스 → 라이브러리**에서 아래 두 API 활성화:
   - `Google Sheets API`
   - `Google Calendar API`
3. **IAM 및 관리자 → 서비스 계정** → 새 서비스 계정 생성
4. 서비스 계정 클릭 → **키 탭** → **키 추가 → 새 키 만들기 → JSON**
5. 다운로드된 `.json` 파일 보관

#### Google 시트 연결
1. Google 시트 새로 생성 (중복 발송 방지 기록용)
2. 시트 URL에서 ID 복사:
   ```
   https://docs.google.com/spreadsheets/d/<여기가 SHEET_ID>/edit
   ```
3. 서비스 계정 이메일(`.json` 파일 내 `client_email`)을 시트에 **편집자**로 공유

#### Google 캘린더 연결
1. Google 캘린더 → 캘린더 설정 → **캘린더 ID** 복사
2. 서비스 계정 이메일을 캘린더에 **조회 권한**으로 공유

---

### 3. 공공데이터포털 API 키 발급

[data.go.kr](https://www.data.go.kr) 회원가입 후:

#### 기상청 API
1. 검색: `기상청_단기예보 조회서비스`
2. **활용신청** → 즉시 승인
3. 마이페이지 → **일반 인증키(디코딩)** 복사

#### 에어코리아 API
1. 검색: `한국환경공단_에어코리아_대기오염정보_조회서비스`
2. **활용신청** → 즉시 승인
3. 마이페이지 → **일반 인증키(디코딩)** 복사

> 두 API가 각각 별도 키입니다.

---

### 4. GitHub Actions 설정

레포 → **Settings → Secrets and variables → Actions** 에서 아래 시크릿 등록:

| Secret 이름 | 값 |
|------------|-----|
| `TELEGRAM_TOKEN` | 텔레그램 봇 토큰 |
| `CHAT_ID` | 텔레그램 채팅 ID |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | 서비스 계정 `.json` 파일 내용 전체 |
| `GOOGLE_SHEET_ID` | Google 시트 ID |
| `GOOGLE_CALENDAR_ID` | Google 캘린더 ID |
| `KMA_API_KEY` | 기상청 API 키 (디코딩) |
| `AIRKOREA_API_KEY` | 에어코리아 API 키 (디코딩) |

---

### 5. 로컬 실행 (선택)

```bash
pip install -r requirements.txt
```

`input/.env` 파일 생성:
```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
GOOGLE_SHEET_ID=...
GOOGLE_APPLICATION_CREDENTIALS=input/service-account.json
GOOGLE_CALENDAR_ID=...
KMA_API_KEY=...
AIRKOREA_API_KEY=...
```

`input/service-account.json` — 서비스 계정 키 파일 배치 후:

```bash
python main.py --force
```

---

## 날씨 설정 변경

현재 **서울 중구** 기준입니다. 다른 지역으로 변경하려면 `main.py`에서 격자 좌표를 수정하세요.

```python
"nx": 60, "ny": 127,   # 서울 중구
```

기상청 격자 좌표는 [기상청 공식 문서](https://www.kma.go.kr/kma/biz/forecast_obs01.jsp)에서 확인할 수 있습니다.

---

## 기술 스택

- **Python 3.11+**
- **GitHub Actions** — 자동 스케줄 실행
- **기상청 단기예보 API** — 날씨
- **에어코리아 API** — 미세먼지 실측
- **yfinance** — 증시 데이터
- **feedparser** — RSS 뉴스 수집
- **deep-translator** — 영문 뉴스 한국어 번역
- **gspread** — Google Sheets 연동
- **python-telegram-bot** — 텔레그램 발송
