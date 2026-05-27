# 코인 자동매매 프로그램 — 업비트/Python 레퍼런스 분석

> 업비트(Upbit) + Python 기준으로 검증된 오픈소스/교재를 조사하고, 실전 봇을 만들 때
> 필요한 구조와 주의점을 정리한 문서.

## 1. 대표 참고 프로젝트

| 프로젝트 | 특징 | 비고 |
|---|---|---|
| `sharebook-kr/pyupbit` | 업비트 API 파이썬 래퍼. 거의 모든 예제의 기반 | 필수 라이브러리 |
| `youtube-jocoding/pyupbit-autotrade` | 변동성 돌파 → +이동평균 → +AI(Prophet) → +Slack 알림 단계별 | 입문 최적 |
| "파이썬을 이용한 비트코인 자동매매" (wikidocs) | 사실상 표준 교재. 환경설정→전략→백테스팅→배포 | 이론+실습 |
| `sharebook-kr/cryptocurrency-trading-bot` (`utrader-multi.py`) | 멀티코인 + 노이즈 필터 + 트레일링 스탑 | 실전형 |
| `showmethecoin/upbit-trader` | PyQt GUI + 웹소켓 실시간 | GUI 참고 |
| `hyeon9698/upbit_bot` | 텔레그램 알림 + 수익 기록 | 운영 참고 |

## 2. 사실상 표준 스택

```
pyupbit        # 거래소 API (시세조회 + 주문)
pandas         # 캔들 데이터 가공
schedule       # 정해진 시각 작업 (선택)
prophet        # AI 가격 예측 (선택)
python-telegram-bot / requests  # 알림 (선택)
```

## 3. 표준 전략 — 래리 윌리엄스 "변동성 돌파"

```
매수 목표가 = 전일 종가 + (전일 고가 - 전일 저가) × k     # k = 0.5 가 표준
```

- 장중 현재가가 목표가를 **돌파**하면 매수
- 하루가 끝나는 시점(종가 직전)에 **무조건 청산**
- 단순하지만 추세 추종으로 검증된 단타 전략

### 확장 패턴 (예제들이 발전시킨 방향)

1. **MA 필터**: `목표가 돌파 AND 현재가 ≥ N일 이동평균` 일 때만 매수 → 하락장 가짜신호 제거
2. **멀티코인 + 노이즈 필터**: KRW마켓에서 노이즈 낮은 코인 N개 선별, 예산 균등배분
3. **트레일링 스탑**: 고점 대비 일정 % 하락 시 익절/손절
4. **AI 예측**: Prophet로 다음날 종가 예측해 매수 게이트로 사용

## 4. 봇 아키텍처 (시간 기반 상태머신)

```
       ┌─────────────────────────────────────────────┐
       │  매 1초 루프 (try/except 로 죽지 않게)         │
       └─────────────────────────────────────────────┘
                          │
        ┌─────────────────┴──────────────────┐
        │ 장중 (start < now < end-10s)         │ 종가 직전 / 장외
        ▼                                      ▼
  포지션 없음 → 돌파+필터 만족 시 매수        보유 중이면 전량 청산
  포지션 보유 → 손절/트레일링 스탑 체크
```

## 5. 실전 봇 필수 구성요소 체크리스트

대부분 입문 예제는 **전략 로직만** 있고 운영 요소가 빠져 있다. 실제로는:

- [x] **키 보안**: access/secret 하드코딩 금지 → `.env` + `python-dotenv`
- [x] **리스크 관리**: 손절, 포지션 크기 제한, 최소 주문금액(5,000원)
- [x] **알림**: 텔레그램/콘솔로 거래 내역 통지
- [x] **예외 안전성**: 네트워크/API 예외에도 루프 유지
- [x] **백테스팅**: 실거래 전 과거검증 + 페이퍼 트레이딩
- [x] **재시작 안전성**: 봇 재기동 시 진입가/당일고점 복구 (`src/state.py`)
- [x] **멀티코인**: 노이즈 기반 종목 선정 + 예산 균등 배분 (`src/selector.py`, `bot.py`)
- [x] **트레일링 스탑**: 당일 고점 대비 하락 청산 (`src/risk.py`)
- [x] **AI 게이트(선택)**: Prophet 예측 기반 매수 필터 (`src/predictor.py`)
- [x] **API rate limit** 대응: 호출 간 최소 간격 + 일봉 TTL 캐시 (`src/ratelimit.py`)
- [x] **백테스트 확장**: 손절/트레일링 시뮬레이션 + 멀티코인 포트폴리오 집계 (`src/backtest.py`)

## 6. 주의사항 (리스크)

- 변동성 돌파는 **상승장에 강하고 횡보/하락장에서 손실** 누적 → MA필터·손절 필수
- 입문 예제는 **교육용**. 그대로 실거래 시 자금 손실 위험. 소액·페이퍼부터.
- pyupbit 일부 API는 버전에 따라 반환 구조가 달라짐 → 최신 버전 확인
- **수수료(0.05%)** 와 슬리피지를 백테스트에 반드시 반영

## 7. 이 저장소의 구현

본 저장소는 위 분석을 바탕으로 다음을 모듈로 분리해 구현했다.

```
config.py              # .env 로딩 / 설정
src/exchange.py        # pyupbit 래퍼 (지연 import 로 격리)
src/strategies/        # 전략 (base + volatility_breakout)
src/risk.py            # 손절 / 트레일링 스탑 / 포지션 사이징
src/selector.py        # 멀티코인 종목 선정 (노이즈 기반)
src/predictor.py       # 선택적 AI 매수 게이트 (Prophet)
src/state.py           # 포지션 상태 영속화 (재시작 복구)
src/notifier.py        # 텔레그램 / 콘솔 알림
src/backtest.py        # 백테스팅 엔진 (수수료 반영)
src/bot.py             # 라이브 멀티코인 매매 루프 (상태머신)
run.py                 # CLI 진입점 (backtest / live)
tests/                 # 단위 테스트 (전략/백테스트/리스크/상태/선정/예측/봇)
```

## 참고 링크

- youtube-jocoding/pyupbit-autotrade — https://github.com/youtube-jocoding/pyupbit-autotrade
- sharebook-kr/pyupbit — https://github.com/sharebook-kr/pyupbit
- sharebook-kr/cryptocurrency-trading-bot — https://github.com/sharebook-kr/cryptocurrency-trading-bot
- 파이썬을 이용한 비트코인 자동매매 (wikidocs) — https://wikidocs.net/21811
- showmethecoin/upbit-trader — https://github.com/showmethecoin/upbit-trader
