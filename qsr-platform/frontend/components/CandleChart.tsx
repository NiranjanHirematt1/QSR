"use client";
import { useEffect, useRef } from "react";
import {
  createChart, ColorType, UTCTimestamp, type IChartApi,
  type SeriesMarker, type Time,
} from "lightweight-charts";
import type { Candle, Trade } from "@/lib/types";

const secs = (iso: string) => Math.floor(new Date(iso).getTime() / 1000) as UTCTimestamp;

export default function CandleChart({ candles, trades = [] }: { candles: Candle[]; trades?: Trade[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart: IChartApi = createChart(el, {
      layout: { background: { type: ColorType.Solid, color: "#0e1117" }, textColor: "#9aa" },
      grid: { vertLines: { color: "#1b2130" }, horzLines: { color: "#1b2130" } },
      rightPriceScale: { borderColor: "#232838" },
      timeScale: { borderColor: "#232838", timeVisible: true },
      height: 440,
      width: el.clientWidth,
    });
    const series = chart.addCandlestickSeries({
      upColor: "#4fd1c5", downColor: "#f56565", borderVisible: false,
      wickUpColor: "#4fd1c5", wickDownColor: "#f56565",
    });
    series.setData(candles.map((c) => ({
      time: c.time as UTCTimestamp, open: c.open, high: c.high, low: c.low, close: c.close,
    })));

    const markers: SeriesMarker<Time>[] = [];
    for (const t of trades) {
      const long = t.side === "BUY";
      markers.push({
        time: secs(t.entry_time), position: long ? "belowBar" : "aboveBar",
        color: "#63b3ed", shape: long ? "arrowUp" : "arrowDown",
        text: `in${t.entry_reason ? " " + t.entry_reason : ""}`,
      });
      markers.push({
        time: secs(t.exit_time), position: long ? "aboveBar" : "belowBar",
        color: t.pnl >= 0 ? "#4fd1c5" : "#f56565", shape: long ? "arrowDown" : "arrowUp",
        text: `${t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(0)}`,
      });
    }
    markers.sort((a, b) => (a.time as number) - (b.time as number));
    series.setMarkers(markers);
    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);
    return () => { ro.disconnect(); chart.remove(); };
  }, [candles, trades]);

  return <div ref={ref} style={{ width: "100%" }} />;
}
