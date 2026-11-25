import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, apiMessage } from "@/lib/api";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("sends the X-Tenant header and returns parsed JSON", async () => {
    const fetchMock = vi.fn(async () => jsonResponse([{ id: "c0", level: 0 }]));
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.communities(0);

    expect(result).toEqual([{ id: "c0", level: 0 }]);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/communities?level=0");
    expect(new Headers(init.headers).get("X-Tenant")).toBe("demo");
  });

  it("throws ApiError with status and backend detail on non-2xx", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "entity not found" }, 404)));

    const error = await api.entity("e_missing").catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, message: "entity not found" });
  });

  it("maps network failures to status 0 and passes AbortSignal through", async () => {
    const fetchMock = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await expect(api.evalReport(controller.signal)).rejects.toMatchObject({ status: 0 });
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.signal).toBe(controller.signal);
  });
});

describe("apiMessage", () => {
  it("formats API errors, unreachable API and unknown errors", () => {
    expect(apiMessage(new ApiError(500, "boom"))).toBe("500 · boom");
    expect(apiMessage(new ApiError(0, "network error"))).toBe("Could not reach the API.");
    expect(apiMessage(new Error("x"))).toBe("Unexpected error.");
  });
});
