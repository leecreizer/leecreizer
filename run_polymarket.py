"""Polymarket 엣지 측정 하니스 — CLI (읽기 전용).

  # 합성 데이터로 즉시 시연 (네트워크 불필요)
  python run_polymarket.py simulate --lag 3 --spread 0.02 --plot out.png

  # 기록된 CSV 분석
  python run_polymarket.py analyze --csv samples.csv --plot out.png

  # 라이브 기록 (사용자 PC 등 네트워크 허용 환경에서만; 주문 안 함, 키 불필요)
  python run_polymarket.py record --symbol BTCUSDT --token-id <YES토큰ID> \
      --horizon 900 --interval 1 --duration 600 --out samples.csv
"""
from __future__ import annotations

import argparse
import sys
import time

from polymarket import CSV_COLUMNS
from polymarket.analyze import load_csv, plot, summarize
from polymarket.simulate import simulate


def cmd_simulate(args: argparse.Namespace) -> None:
    df = simulate(
        duration_sec=args.duration,
        interval_sec=args.interval,
        lag_sec=args.lag,
        spread=args.spread,
        cost=args.cost,
        annual_vol=args.vol,
        seed=args.seed,
    )
    if args.out:
        df.to_csv(args.out, index=False)
        print(f"기록: {args.out} ({len(df)} 행)")
    print(f"== 시뮬레이션 (lag={args.lag}s, spread={args.spread}, cost={args.cost}) ==")
    print(summarize(df).text())
    if args.plot:
        print(f"차트 저장: {plot(df, args.plot)}")


def cmd_analyze(args: argparse.Namespace) -> None:
    df = load_csv(args.csv)
    missing = [c for c in CSV_COLUMNS if c not in df.columns]
    if missing:
        sys.exit(f"CSV 컬럼 누락: {missing}")
    print(f"== 분석 {args.csv} ==")
    print(summarize(df).text())
    if args.plot:
        print(f"차트 저장: {plot(df, args.plot)}")


def cmd_record(args: argparse.Namespace) -> None:
    try:
        from polymarket.feeds import BinanceFeed, PolymarketFeed
        from polymarket.recorder import Recorder
    except BaseException as e:  # noqa: BLE001
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        sys.exit(f"피드 로드 실패: {e}")

    binance = BinanceFeed()
    pm = PolymarketFeed()
    try:
        strike = binance.get_price(args.symbol)
    except Exception as e:  # noqa: BLE001
        sys.exit(
            "바이낸스 시세 조회 실패(이 환경은 외부 네트워크가 제한될 수 있음).\n"
            f"  → 네트워크 허용 환경에서 실행하거나 simulate 를 쓰세요. 원인: {e}"
        )
    rec = Recorder(
        binance,
        pm,
        symbol=args.symbol,
        token_id=args.token_id,
        strike=strike,
        expiry_ts=time.time() + args.horizon,
        interval=args.interval,
        cost=args.cost,
    )
    print(f"기록 시작: strike={strike}, {args.duration}s 동안 {args.interval}s 간격 (읽기 전용)")
    n = rec.run(args.duration, args.out)
    print(f"완료: {n} 행 -> {args.out}")
    print("이제: python run_polymarket.py analyze --csv " + args.out + " --plot out.png")


def main() -> None:
    p = argparse.ArgumentParser(description="Polymarket 지연-엣지 측정 하니스 (읽기 전용)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="합성 데이터로 시연/검증")
    s.add_argument("--duration", type=int, default=900)
    s.add_argument("--interval", type=float, default=1.0)
    s.add_argument("--lag", type=float, default=3.0)
    s.add_argument("--spread", type=float, default=0.02)
    s.add_argument("--cost", type=float, default=0.0)
    s.add_argument("--vol", type=float, default=0.8)
    s.add_argument("--seed", type=int, default=42)
    s.add_argument("--out", default=None)
    s.add_argument("--plot", default=None)
    s.set_defaults(func=cmd_simulate)

    a = sub.add_parser("analyze", help="기록된 CSV 분석")
    a.add_argument("--csv", required=True)
    a.add_argument("--plot", default=None)
    a.set_defaults(func=cmd_analyze)

    r = sub.add_parser("record", help="라이브 기록 (네트워크 허용 환경, 주문 안 함)")
    r.add_argument("--symbol", default="BTCUSDT")
    r.add_argument("--token-id", required=True, help="Polymarket YES/UP outcome 토큰 ID")
    r.add_argument("--horizon", type=float, default=900, help="계약 잔여시간(초)")
    r.add_argument("--interval", type=float, default=1.0)
    r.add_argument("--duration", type=float, default=600)
    r.add_argument("--cost", type=float, default=0.0)
    r.add_argument("--out", default="samples.csv")
    r.set_defaults(func=cmd_record)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
