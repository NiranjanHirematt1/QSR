import "./globals.css";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata = { title: "QSR — Strategy Research", description: "Backtesting research" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <span className="brand">QSR</span>
          <Link href="/">Dashboard</Link>
          <Link href="/compare">Compare</Link>
          <span className="pill">forex / futures · event-driven · multi-timeframe</span>
        </nav>
        {children}
      </body>
    </html>
  );
}
