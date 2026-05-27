# 코인 자동매매 프로그램 (업비트 / Python)

업비트 변동성 돌파 전략 기반 자동매매 스타터. 전략·주문·리스크·알림·백테스트를
모듈로 분리한 구조입니다. 설계 근거와 레퍼런스 분석은 [`docs/analysis.md`](docs/analysis.md) 참고.

> ⚠️ 교육용 스타터입니다. 실거래는 자금 손실 위험이 있으니 반드시 백테스트 →
> 소액 → 페이퍼 트레이딩 순으로 검증하세요.

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env   # 업비트 API 키 등 입력
```

## 백테스트

```bash
# 업비트에서 최근 365일 일봉을 받아 검증 (네트워크 필요)
python run.py backtest --days 365 --k 0.5 --ma 0

# CSV(인덱스=날짜, open/high/low/close/volume)로 검증
python run.py backtest --csv data/btc.csv

# 합성 데이터로 즉시 동작 확인 (네트워크 불필요)
python scripts/demo_backtest.py
```

## 실거래

```bash
python run.py live   # .env 의 API 키 사용. 실거래 주의!
```

## 구조

```
config.py              # .env 로딩
src/exchange.py        # pyupbit 래퍼 (지연 import 로 격리)
src/strategies/        # 전략 (base + volatility_breakout)
src/risk.py            # 손절 / 트레일링 스탑 / 포지션 사이징
src/selector.py        # 멀티코인 종목 선정 (노이즈 기반)
src/predictor.py       # 선택적 AI 매수 게이트 (Prophet)
src/state.py           # 포지션 상태 영속화 (재시작 복구)
src/notifier.py        # 텔레그램 / 콘솔 알림
src/backtest.py        # 백테스팅 엔진 (수수료 반영)
src/bot.py             # 라이브 멀티코인 매매 루프 (시간 기반 상태머신)
run.py                 # CLI 진입점 (backtest / live)
tests/                 # 단위 테스트
```

## 주요 기능

- **멀티코인**: `TICKERS=KRW-BTC,KRW-ETH,KRW-SOL` 로 여러 코인 동시 매매, 예산 균등 배분
- **트레일링 스탑**: `TRAIL_STOP_PCT` 설정 시 당일 고점 대비 하락에 청산 (최소수익 조건 포함)
- **AI 게이트**: `USE_AI_GATE=true` 시 Prophet 예측가가 현재가 이상일 때만 매수 (prophet 설치 필요)
- **상태 영속화**: 진입가·당일고점을 `state.json` 에 저장해 봇 재시작 시 복구

## 테스트

```bash
pytest -q
```

## 전략 요약

```
매수 목표가 = 전일 종가 + (전일 고가 - 전일 저가) × k
장중 현재가 ≥ 목표가  → 매수 (선택: 현재가 ≥ N일 이동평균)
종가 직전              → 전량 청산
진입가 대비 -STOP_LOSS_PCT → 손절
```
