import { describe, expect, it, vi } from "vitest";
import { watchRun } from "./useRefresh";

const run = (status: string) => ({ runId: "r1", status, alreadyRunning: false });

describe("watchRun", () => {
  it("startuje run i odpytuje status aż do sukcesu", async () => {
    const status = vi.fn().mockResolvedValueOnce(run("STARTED")).mockResolvedValue(run("SUCCESS"));
    expect(await watchRun({ start: async () => run("QUEUED"), status }, 1)).toBe("success");
    expect(status).toHaveBeenCalledTimes(2);
  });
  it("nie odpytuje, gdy start od razu zwraca zakończony run", async () => {
    const status = vi.fn();
    expect(await watchRun({ start: async () => run("SUCCESS"), status }, 1)).toBe("success");
    expect(status).not.toHaveBeenCalled();
  });
  it("błąd runu to failure, a błąd komunikacji to unavailable", async () => {
    expect(await watchRun({ start: async () => run("QUEUED"), status: async () => run("FAILURE") }, 1)).toBe("failure");
    expect(await watchRun({ start: async () => run("QUEUED"), status: async () => run("CANCELED") }, 1)).toBe("failure");
    expect(await watchRun({ start: () => Promise.reject(new Error("502")), status: vi.fn() }, 1)).toBe("unavailable");
    expect(await watchRun({ start: async () => run("QUEUED"), status: () => Promise.reject(new Error("net")) }, 1)).toBe("unavailable");
  });
  it("przerywa odpytywanie po odmontowaniu", async () => {
    const status = vi.fn();
    expect(await watchRun({ start: async () => run("QUEUED"), status }, 1, () => true)).toBe("cancelled");
    expect(status).not.toHaveBeenCalled();
  });
});
