import type { Metadata, Viewport } from "next";

import { NavBar } from "@/components/NavBar";

import "./globals.css";

export const metadata: Metadata = {
  title: "Alibi: feedback for your lifts",
  description: "Upload a set, get one fix and one cue, backed by measurements from your video.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <NavBar />
        <main className="mx-auto w-full max-w-xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
