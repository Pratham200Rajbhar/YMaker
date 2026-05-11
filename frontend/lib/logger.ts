import { API_BASE } from "./api";

type LogLevel = "info" | "warn" | "error";

interface LogEntry {
  level: LogLevel;
  message: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

class Logger {
  private buffer: LogEntry[] = [];
  private flushInterval = 5000; // 5 seconds
  private maxBufferSize = 50;
  private timer: NodeJS.Timeout | null = null;

  constructor() {
    if (typeof window !== "undefined") {
      this.startTimer();
    }
  }

  private startTimer() {
    this.timer = setInterval(() => this.flush(), this.flushInterval);
  }

  private async flush() {
    if (this.buffer.length === 0) return;

    const logsToFlush = [...this.buffer];
    this.buffer = [];

    try {
      const response = await fetch(`${API_BASE}/logs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ logs: logsToFlush }),
      });

      if (!response.ok) {
        console.error("Failed to flush logs to backend", await response.text());
        // Put back in buffer if failed, but don't overflow
        if (this.buffer.length < this.maxBufferSize) {
           this.buffer = [...logsToFlush, ...this.buffer].slice(0, this.maxBufferSize);
        }
      }
    } catch (error) {
      console.error("Error flushing logs:", error);
    }
  }

  private log(level: LogLevel, message: string, metadata?: Record<string, any>) {
    const entry: LogEntry = {
      level,
      message,
      timestamp: new Date().toISOString(),
      metadata: {
        ...metadata,
        url: typeof window !== "undefined" ? window.location.href : "server",
        userAgent: typeof navigator !== "undefined" ? navigator.userAgent : "unknown",
      },
    };

    // Console output for developers
    const consoleMethod = level === "error" ? "error" : level === "warn" ? "warn" : "log";
    console[consoleMethod](`[${level.toUpperCase()}] ${message}`, metadata || "");

    this.buffer.push(entry);

    if (this.buffer.length >= this.maxBufferSize) {
      this.flush();
    }
  }

  info(message: string, metadata?: Record<string, any>) {
    this.log("info", message, metadata);
  }

  warn(message: string, metadata?: Record<string, any>) {
    this.log("warn", message, metadata);
  }

  error(message: string, metadata?: Record<string, any>) {
    this.log("error", message, metadata);
  }
}

export const logger = new Logger();
