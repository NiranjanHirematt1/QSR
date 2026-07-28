"use client";
import { useEffect, useRef } from "react";
import { createChart, ColorType, UTCTimestamp, type IChartApi } from "lightweight-charts";
import type { EquityPoint } from "@/lib/types";

export interface EquitySeries { name: string; color: string; data: EquityPoint[]; }

export default function EquityChart({ series, height = 260 }: { series: EquitySeries[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart: IChartApi = createChart(el, {
      layout: { background: { type: ColorType.Solid, color: "#0e1117" }, textColor: "#9aa" },
      grid: { vertLines: { color: "#1b2130" }, horzLines: { color: "#1b2130" } },
      rightPriceScale: { borderColor: "#232838" },
      timeScale: { borderColor: "#232838", timeVisible: true },
      height, width: el.clientWidth,
    });
    for (const s of series) {
      const line = chart.addLineSeries({ color: s.color, lineWidth: 2, title: s.name });
      const seen = new Set<number>();
      const data = s.data
        .map(([iso, v]) => ({ time: Math.floor(new Date(iso).getTime() / 1000) as UTCTimestamp, value: v }))
        .filter((p) => { if (seen.has(p.time as number)) return false; seen.add(p.time as number); return true; });
      line.setData(data);
    }
    chart.timeScale().fitContent();
    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);
    return () => { ro.disconnect(); chart.remove(); };
  }, [series, height]);

  return <div ref={ref} style={{ width: "100%" }} />;
}
