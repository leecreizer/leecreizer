"""기록된 CSV 를 분석: 갭 분포, 비용 반영 후 엣지가 남는지 판정 + 차트."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Summary:
    n: int
    duration_sec: float
    gap_mean: float
    gap_std: float
    gap_abs_p95: float
    edge_pos_fraction: float   # 순엣지 > 0 인 표본 비율
    edge_pos_mean: float       # 양(+)의 순엣지 평균 크기
    verdict: str

    def text(self) -> str:
        return (
            f"표본={self.n}  관측시간={self.duration_sec:.0f}s\n"
            f"갭 평균={self.gap_mean:+.4f}  표준편차={self.gap_std:.4f}  |갭| p95={self.gap_abs_p95:.4f}\n"
            f"순엣지>0 비율={self.edge_pos_fraction*100:.1f}%  "
            f"양의 순엣지 평균={self.edge_pos_mean:+.4f}\n"
            f"판정: {self.verdict}"
        )


def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def summarize(df: pd.DataFrame) -> Summary:
    n = len(df)
    duration = float(df["ts"].iloc[-1] - df["ts"].iloc[0]) if n > 1 else 0.0
    gap = df["gap"]
    pos = df[df["net_edge"] > 0]["net_edge"]
    frac = len(pos) / n if n else 0.0
    pos_mean = float(pos.mean()) if len(pos) else 0.0

    # 보수적 판정 휴리스틱
    if frac >= 0.05 and pos_mean >= 0.01:
        verdict = "엣지 후보 있음 — 그래도 라이브 체결/깊이/지연 추가 검증 필수"
    elif frac > 0:
        verdict = "엣지 미미 — 비용·스프레드 반영 시 사실상 무의미"
    else:
        verdict = "엣지 없음 — 이 데이터로는 수익 기회 관측 안 됨"

    return Summary(
        n=n,
        duration_sec=duration,
        gap_mean=float(gap.mean()) if n else 0.0,
        gap_std=float(gap.std()) if n else 0.0,
        gap_abs_p95=float(gap.abs().quantile(0.95)) if n else 0.0,
        edge_pos_fraction=frac,
        edge_pos_mean=pos_mean,
        verdict=verdict,
    )


def plot(df: pd.DataFrame, out_png: str) -> str:
    import matplotlib

    matplotlib.use("Agg")  # 헤드리스
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7))
    ax1.plot(df["ts"], df["fair_prob"], label="Binance fair prob", color="tab:blue")
    ax1.plot(df["ts"], df["pm_mid"], label="Polymarket mid", color="tab:red", alpha=0.8)
    ax1.set_title("Fair probability vs Polymarket mid (gap = the edge)")
    ax1.set_ylabel("probability")
    ax1.legend()

    ax2.hist(df["gap"], bins=50, color="tab:purple", alpha=0.8)
    ax2.axvline(0, color="black", lw=1)
    ax2.set_title("Gap distribution")
    ax2.set_xlabel("fair_prob - pm_mid")

    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)
    return out_png
