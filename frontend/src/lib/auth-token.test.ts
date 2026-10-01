import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { _resetTokenCacheForTests, getApiToken } from "@/lib/auth-token";

const OIDC_ENV = {
  OIDC_TOKEN_URL: "http://authentik.test/application/o/token/",
  OIDC_CLIENT_ID: "uw-client",
  OIDC_CLIENT_SECRET: "uw-secret",
  OIDC_SCOPE: "underwriting:read underwriting:write",
};

function setOidcEnv(): void {
  for (const [k, v] of Object.entries(OIDC_ENV)) process.env[k] = v;
}
function clearOidcEnv(): void {
  for (const k of Object.keys(OIDC_ENV)) delete process.env[k];
}

function mockTokenResponse(accessToken: string, expiresIn?: number) {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ access_token: accessToken, ...(expiresIn != null ? { expires_in: expiresIn } : {}) }),
  } as unknown as Response);
}

beforeEach(() => {
  _resetTokenCacheForTests();
  clearOidcEnv();
  vi.restoreAllMocks();
});
afterEach(() => clearOidcEnv());

describe("getApiToken", () => {
  it("returns null when OIDC is not configured (dev — backend auth off)", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    await expect(getApiToken()).resolves.toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("mints a client-credentials token with the configured scope", async () => {
    setOidcEnv();
    const fetchSpy = mockTokenResponse("tok-1", 300);
    vi.stubGlobal("fetch", fetchSpy);

    await expect(getApiToken()).resolves.toBe("tok-1");

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe(OIDC_ENV.OIDC_TOKEN_URL);
    const body = (init as RequestInit).body as URLSearchParams;
    expect(body.get("grant_type")).toBe("client_credentials");
    expect(body.get("client_id")).toBe("uw-client");
    expect(body.get("scope")).toBe("underwriting:read underwriting:write");
  });

  it("caches the token until shortly before expiry (no second fetch)", async () => {
    setOidcEnv();
    const fetchSpy = mockTokenResponse("tok-cache", 300);
    vi.stubGlobal("fetch", fetchSpy);

    const now = vi.fn<() => number>().mockReturnValue(0);
    await getApiToken(now);
    now.mockReturnValue(100_000); // +100s, well within 300s - 30s skew
    await expect(getApiToken(now)).resolves.toBe("tok-cache");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("refreshes after expiry (minus skew)", async () => {
    setOidcEnv();
    const fetchSpy = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ access_token: "old", expires_in: 300 }) } as unknown as Response)
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ access_token: "new", expires_in: 300 }) } as unknown as Response);
    vi.stubGlobal("fetch", fetchSpy);

    const now = vi.fn<() => number>().mockReturnValue(0);
    await expect(getApiToken(now)).resolves.toBe("old");
    now.mockReturnValue(280_000); // past 300s - 30s skew → refresh
    await expect(getApiToken(now)).resolves.toBe("new");
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("throws on a non-OK token endpoint response", async () => {
    setOidcEnv();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as unknown as Response));
    await expect(getApiToken()).rejects.toThrow(/401/);
  });
});
