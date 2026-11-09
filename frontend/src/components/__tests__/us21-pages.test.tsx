import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HistoryPage from "@/app/history/page";
import SettingsPage from "@/app/settings/page";
import { api } from "@/lib/api";
import { getToken, setSession } from "@/lib/session";

const navigation = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, history: vi.fn(), deleteUpload: vi.fn(), deleteAccount: vi.fn() } };
});

beforeEach(() => { vi.resetAllMocks(); });

describe("US-21 deletion pages", () => {
  it("us21_history_removes_every_analysis_of_the_deleted_upload", async () => {
    const row = { analysis_id: "a1", upload_id: "u1", created_at: "2026-11-09T12:00:00Z", lift: "squat" as const,
      lift_label: "Squat", rep_count: 5, top_fix_title: null, status: "done" as const,
      final_status: "passed_first_try" as const, status_label: "Analyzed" };
    vi.mocked(api.history).mockResolvedValue({ items: [row, { ...row, analysis_id: "a2" }] });
    vi.mocked(api.deleteUpload).mockResolvedValue(undefined);
    render(<HistoryPage />);
    await userEvent.click((await screen.findAllByRole("button", { name: "Delete upload" }))[0]);
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete upload" }));
    expect(api.deleteUpload).toHaveBeenCalledWith("u1", null);
    expect(await screen.findByText("No uploads yet.")).toBeInTheDocument();
  });

  it("us21_settings_deletes_the_account_clears_its_cookie_and_returns_to_login", async () => {
    setSession("test-session");
    vi.mocked(api.deleteAccount).mockResolvedValue(undefined);
    render(<SettingsPage />);
    await userEvent.click(screen.getByRole("button", { name: "Delete account" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete account" }));
    expect(api.deleteAccount).toHaveBeenCalledWith("test-session");
    expect(getToken()).toBeNull();
    expect(navigation.replace).toHaveBeenCalledWith("/login?deleted=1");
  });
});
