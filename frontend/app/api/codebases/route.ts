import { NextResponse } from "next/server";

const API_URL = process.env.LEGACYLENS_API_URL;
const TIMEOUT_MS = 15_000;

export async function GET() {
  if (!API_URL) {
    return NextResponse.json(
      { error: "Backend API URL not configured" },
      { status: 503 }
    );
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const response = await fetch(`${API_URL}/api/codebases`, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      const text = await response.text();
      return NextResponse.json(
        { error: text || `Backend returned ${response.status}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") {
      return NextResponse.json(
        {
          error:
            "Request timed out. The server may be starting up — please try again in a moment.",
        },
        { status: 504 }
      );
    }

    const message =
      err instanceof Error ? err.message : "Failed to reach backend";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
