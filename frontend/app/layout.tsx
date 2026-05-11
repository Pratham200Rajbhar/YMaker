import type { Metadata } from "next";
import "./globals.css";

import LoggerProvider from "@/components/LoggerProvider";

export const metadata: Metadata = {
  title: "MakeVideo",
  description: "AI-powered YouTube production workflow"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <LoggerProvider>
          {children}
        </LoggerProvider>
      </body>
    </html>
  );
}
