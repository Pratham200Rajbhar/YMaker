"use client";

import { useEffect } from "react";
import { logger } from "@/lib/logger";

export default function LoggerProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const handleError = (event: ErrorEvent) => {
      logger.error("Uncaught error", {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error?.toString(),
      });
    };

    const handleRejection = (event: PromiseRejectionEvent) => {
      logger.error("Unhandled promise rejection", {
        reason: event.reason?.toString(),
      });
    };

    window.addEventListener("error", handleError);
    window.addEventListener("unhandledrejection", handleRejection);

    return () => {
      window.removeEventListener("error", handleError);
      window.removeEventListener("unhandledrejection", handleRejection);
    };
  }, []);

  return <>{children}</>;
}
