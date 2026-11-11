import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentType } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminPage from "@/app/admin/page";
import ResultsPage from "@/app/results/[id]/page";
import { ApiError, api } from "@/lib/api";

const navigation = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "a1" }), useRouter: () => navigation }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, analysis: vi.fn(), adminAnalyses: vi.fn(), adminErrors: vi.fn(),
    adminCosts: vi.fn(), adminUsage: vi.fn(), adminUploads: vi.fn(), removeUpload: vi.fn(), moderationLog: vi.fn() } };
});

type Mocked = Record<string, ReturnType<typeof vi.fn>>;
const mocked = api as unknown as Mocked;

// Loaded at run time so each test reports its own failure while the page doesn't exist yet.
const PAGE = "@/app/admin/moderation/page";
async function renderModeration() {
  const { default: Page } = (await import(/* @vite-ignore */ PAGE)) as { default: ComponentType };
  render(<Page />);
}

const usage = { start: "2026-11-01", end: "2026-11-03", removals: 1, totals: { signups: 3, uploads: 4 },
  days: [{ date: "2026-11-01", signups: 2, uploads: 1 }, { date: "2026-11-02", signups: 0, uploads: 0 },
    { date: "2026-11-03", signups: 1, uploads: 3 }] };

const row = (n: number, extra: object = {}) => ({ upload_id: `u${n}`, analysis_id: `a${n}`, created_at: `2026-11-0${n}T12:00:00Z`,
  lift: "squat", lift_label: "Squat", user_email: `lifter${n}@virginia.edu`, filename: "set.mp4", status_label: "Analyzed", ...extra });

const entry = { id: "m1", upload_id: "u9", analysis_ids: ["a9"], lift: "squat", owner_email: "x@virginia.edu",
  removed_by_email: "coach@virginia.edu", reason: "off_topic", reason_label: "Off-topic", note: null,
  removed_at: "2026-11-02T15:00:00Z" };

beforeEach(() => {
  vi.resetAllMocks();
  mocked.adminUsage.mockResolvedValue(usage);
  mocked.adminUploads.mockResolvedValue({ items: [row(1), row(2, { lift: "bench_press", lift_label: "Bench Press" })] });
  mocked.moderationLog.mockResolvedValue({ items: [entry] });
  mocked.adminAnalyses.mockResolvedValue({ items: [] });
  mocked.adminErrors.mockResolvedValue({ counts: {} });
  mocked.adminCosts.mockRejectedValue(new ApiError(0, "Network error"));
});

describe("US-27 usage", () => {
  it("us27_shows_signups_and_uploads_per_day_with_totals", async () => {
    await renderModeration();
    const region = await screen.findByRole("region", { name: "Sign-ups and uploads" });
    const rows = within(region).getAllByRole("row");
    const cells = (r: HTMLElement) => within(r).getAllByRole("cell").map((c) => c.textContent);
    expect(cells(rows[1])).toEqual(["Nov 1, 2026", "2", "1"]);
    expect(cells(rows[3])).toEqual(["Nov 3, 2026", "1", "3"]);
    expect(within(region).getByText("Total sign-ups").nextSibling).toHaveTextContent("3");
    expect(within(region).getByText("Total uploads").nextSibling).toHaveTextContent("4");
    expect(region).toHaveTextContent("1 upload removed by moderators in this range");
  });

  it("us27_choosing_dates_reloads_usage_and_uploads", async () => {
    await renderModeration();
    const usageRegion = await screen.findByRole("region", { name: "Sign-ups and uploads" });
    await within(usageRegion).findByText("Total sign-ups");
    const from = within(usageRegion).getByLabelText("From");
    await userEvent.clear(from);
    await userEvent.type(from, "2026-10-01");
    await userEvent.click(within(usageRegion).getByRole("button", { name: "Show" }));
    expect(mocked.adminUsage).toHaveBeenLastCalledWith("2026-10-01", "2026-11-03", null);
    expect(mocked.adminUploads).toHaveBeenLastCalledWith({ start: "2026-10-01", end: "2026-11-03" }, null);
  });

  it("us27_admin_page_links_to_usage_and_moderation", async () => {
    render(<AdminPage />);
    expect(await screen.findByRole("link", { name: "Usage and moderation" })).toHaveAttribute("href", "/admin/moderation");
  });
});

describe("US-27 upload list", () => {
  it("us27_lists_uploads_with_date_lift_owner_status_and_a_link_to_the_analysis", async () => {
    await renderModeration();
    const region = await screen.findByRole("region", { name: "Uploads" });
    const first = (await within(region).findAllByRole("row"))[1];
    expect(first).toHaveTextContent("Nov 1, 2026");
    expect(first).toHaveTextContent("Squat");
    expect(first).toHaveTextContent("lifter1@virginia.edu");
    expect(first).toHaveTextContent("Analyzed");
    expect(within(first).getByRole("link", { name: "Analysis" })).toHaveAttribute("href", "/admin/analyses/a1");
  });

  it("us27_filtering_by_lift_reloads_the_list", async () => {
    await renderModeration();
    const region = await screen.findByRole("region", { name: "Uploads" });
    await within(region).findAllByRole("row");
    await userEvent.selectOptions(within(region).getByLabelText("Lift"), "bench_press");
    expect(mocked.adminUploads).toHaveBeenLastCalledWith({ start: "2026-11-01", end: "2026-11-03", lift: "bench_press" }, null);
  });
});

describe("US-27 removing an upload", () => {
  it("us27_remove_asks_for_confirmation_and_a_reason_before_removing", async () => {
    await renderModeration();
    const region = await screen.findByRole("region", { name: "Uploads" });
    await userEvent.click((await within(region).findAllByRole("button", { name: "Remove" }))[0]);
    const dialog = screen.getByRole("dialog", { name: "Remove this upload?" });
    expect(mocked.removeUpload).not.toHaveBeenCalled();
    expect(within(dialog).getByRole("button", { name: "Remove upload" })).toBeDisabled();
    expect(within(dialog).getAllByRole("radio").map((r) => r.getAttribute("value"))).toEqual(["off_topic", "inappropriate", "other"]);
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mocked.removeUpload).not.toHaveBeenCalled();
  });

  it("us27_confirmed_removal_takes_the_upload_off_the_list_and_logs_it", async () => {
    mocked.removeUpload.mockResolvedValue({ ...entry, id: "m2", upload_id: "u1", owner_email: "lifter1@virginia.edu",
      reason: "other", reason_label: "Other", note: "Not a lift" });
    await renderModeration();
    const region = await screen.findByRole("region", { name: "Uploads" });
    await userEvent.click((await within(region).findAllByRole("button", { name: "Remove" }))[0]);
    const dialog = screen.getByRole("dialog", { name: "Remove this upload?" });
    await userEvent.click(within(dialog).getByLabelText("Other"));
    await userEvent.type(within(dialog).getByLabelText("Note (optional)"), "Not a lift");
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove upload" }));
    expect(mocked.removeUpload).toHaveBeenCalledWith("u1", "other", "Not a lift", null);
    expect(await within(region).findAllByRole("row")).toHaveLength(2);
    expect(within(region).queryByText("lifter1@virginia.edu")).not.toBeInTheDocument();
    const log = screen.getByRole("region", { name: "Moderation log" });
    expect(await within(log).findByText(/lifter1@virginia.edu/)).toBeInTheDocument();
    expect(log).toHaveTextContent("Other: Not a lift");
  });

  it("us27_a_failed_removal_keeps_the_dialog_open_with_the_reason", async () => {
    mocked.removeUpload.mockRejectedValue(new ApiError(409, "Wait for analyses to finish before deleting. Then try again."));
    await renderModeration();
    const region = await screen.findByRole("region", { name: "Uploads" });
    await userEvent.click((await within(region).findAllByRole("button", { name: "Remove" }))[0]);
    const dialog = screen.getByRole("dialog", { name: "Remove this upload?" });
    await userEvent.click(within(dialog).getByLabelText("Off-topic"));
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove upload" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Wait for analyses to finish");
    expect(within(region).getByText("lifter1@virginia.edu")).toBeInTheDocument();
  });

  it("us27_moderation_log_shows_who_removed_what_when_and_why", async () => {
    await renderModeration();
    const log = await screen.findByRole("region", { name: "Moderation log" });
    const item = await within(log).findByRole("listitem");
    expect(item).toHaveTextContent("Nov 2, 2026");
    expect(item).toHaveTextContent("coach@virginia.edu");
    expect(item).toHaveTextContent("x@virginia.edu");
    expect(item).toHaveTextContent("Off-topic");
  });

  it("us27_non_admins_see_admins_only", async () => {
    mocked.adminUsage.mockRejectedValue(new ApiError(403, "Admins only"));
    mocked.adminUploads.mockRejectedValue(new ApiError(403, "Admins only"));
    mocked.moderationLog.mockRejectedValue(new ApiError(403, "Admins only"));
    await renderModeration();
    expect(await screen.findByRole("heading", { name: "403: Admins only" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Uploads" })).not.toBeInTheDocument();
  });
});

describe("US-27 what the owner sees", () => {
  it("us27_owner_sees_the_upload_was_removed_by_a_moderator", async () => {
    mocked.analysis.mockRejectedValue(new ApiError(410, "This upload was removed by a moderator. Reason: Off-topic."));
    render(<ResultsPage />);
    expect(await screen.findByRole("heading", { name: "This upload was removed by a moderator" })).toBeInTheDocument();
    expect(screen.getByText(/Reason: Off-topic/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to history" })).toHaveAttribute("href", "/history");
  });
});
