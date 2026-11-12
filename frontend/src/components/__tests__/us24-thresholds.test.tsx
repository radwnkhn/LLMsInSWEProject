import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentType } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "@/lib/api";
import type { AdminFault, AdminFaultLift, ThresholdChange } from "@/lib/types";

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, adminFaults: vi.fn(), updateFault: vi.fn(), addFault: vi.fn(),
    thresholdChanges: vi.fn() } };
});

const PAGE = "@/app/admin/faults/page";
async function renderPage() {
  const { default: Page } = (await import(/* @vite-ignore */ PAGE)) as { default: ComponentType };
  render(<Page />);
}

const fault = (overrides: Partial<AdminFault> = {}): AdminFault => ({
  lift: "squat", id: "knee_cave", name: "Knees cave inward", short_name: "knee cave", category: "safety", safety: true,
  metric: "knee_valgus_deg", metric_label: "valgus", threshold: 10, direction: "above", unit: "°", enabled: true,
  threshold_min: 0, threshold_max: 180, ...overrides,
});

const LIFTS: AdminFaultLift[] = [
  { lift: "squat", lift_label: "Squat",
    faults: [fault(), fault({ id: "bar_path_drift", name: "Bar drifts forward and back", short_name: "bar drift",
      category: "technique", safety: false, metric: "bar_drift_ratio", metric_label: "bar drift", threshold: 0.25,
      unit: "", threshold_min: 0, threshold_max: 2 })],
    metrics: [{ metric: "knee_valgus_deg", label: "valgus", unit: "°" }] },
];

const CHANGE: ThresholdChange = {
  lift: "squat", lift_label: "Squat", fault_id: "knee_cave", fault_name: "Knees cave inward", unit: "°",
  old_threshold: 10, new_threshold: 12, changed_by_email: "coach@virginia.edu", changed_at: "2026-11-12T15:04:00+00:00",
};

function region(name: string) {
  return screen.findByRole("region", { name });
}

async function editThreshold(rowIndex: number, value: string) {
  const squat = await region("Squat faults");
  await userEvent.click(within(squat).getAllByRole("button", { name: "Edit" })[rowIndex]);
  const input = within(squat).getByLabelText(/^Threshold/);
  await userEvent.clear(input);
  if (value) await userEvent.type(input, value);
  await userEvent.click(within(squat).getByRole("button", { name: "Save" }));
  return squat;
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.adminFaults).mockResolvedValue({ lifts: structuredClone(LIFTS) });
  vi.mocked(api.thresholdChanges).mockResolvedValue({ items: [] });
});

describe("US-24 threshold editing", () => {
  it("us24_edit_form_shows_the_current_threshold_with_its_unit_and_allowed_range", async () => {
    await renderPage();
    const squat = await region("Squat faults");
    await userEvent.click(within(squat).getAllByRole("button", { name: "Edit" })[0]);
    const input = within(squat).getByLabelText(/^Threshold/);
    expect(input).toHaveValue(10);
    expect(within(squat).getByText("Allowed: 0 to 180°")).toBeInTheDocument();
  });

  it("us24_saving_sends_the_new_threshold_and_shows_the_new_rule", async () => {
    vi.mocked(api.updateFault).mockResolvedValue(fault({ threshold: 12 }));
    await renderPage();
    const squat = await editThreshold(0, "12");
    expect(api.updateFault).toHaveBeenCalledWith("squat", "knee_cave",
      { name: "Knees cave inward", short_name: "knee cave", threshold: 12 }, null);
    expect(await within(squat).findByText("above 12°")).toBeInTheDocument();
  });

  it("us24_saving_without_changing_the_threshold_does_not_send_it", async () => {
    vi.mocked(api.updateFault).mockResolvedValue(fault());
    await renderPage();
    const squat = await region("Squat faults");
    await userEvent.click(within(squat).getAllByRole("button", { name: "Edit" })[0]);
    expect(within(squat).getByLabelText(/^Threshold/)).toHaveValue(10);
    await userEvent.click(within(squat).getByRole("button", { name: "Save" }));
    expect(api.updateFault).toHaveBeenCalledWith("squat", "knee_cave", { name: "Knees cave inward", short_name: "knee cave" }, null);
  });

  it.each([["", "Threshold must be a number"], ["181", "Threshold must be between 0 and 180"],
    ["-1", "Threshold must be between 0 and 180"]])(
    "us24_invalid_threshold_%s_is_rejected_before_saving", async (value, message) => {
      await renderPage();
      const squat = await editThreshold(0, value);
      expect(await within(squat).findByRole("alert")).toHaveTextContent(message);
      expect(api.updateFault).not.toHaveBeenCalled();
    });

  it("us24_ratio_thresholds_use_their_own_range", async () => {
    await renderPage();
    const squat = await editThreshold(1, "2.5");
    expect(await within(squat).findByRole("alert")).toHaveTextContent("Threshold must be between 0 and 2");
    expect(api.updateFault).not.toHaveBeenCalled();
  });

  it("us24_a_threshold_the_api_rejects_shows_its_reason", async () => {
    vi.mocked(api.updateFault).mockRejectedValue(new ApiError(422, "Threshold must be between 0 and 180"));
    vi.mocked(api.adminFaults).mockResolvedValue({ lifts: [{ ...structuredClone(LIFTS[0]),
      faults: [fault({ threshold_min: undefined, threshold_max: undefined })] }] });
    await renderPage();
    const squat = await editThreshold(0, "500");
    expect(await within(squat).findByRole("alert")).toHaveTextContent("between 0 and 180");
  });
});

describe("US-24 threshold change log", () => {
  it("us24_change_log_lists_who_changed_what_when_from_and_to", async () => {
    vi.mocked(api.thresholdChanges).mockResolvedValue({ items: [CHANGE] });
    await renderPage();
    const log = await region("Threshold changes");
    const [row] = within(log).getAllByRole("row").slice(1);
    expect(row).toHaveTextContent("Knees cave inward");
    expect(row).toHaveTextContent("Squat");
    expect(row).toHaveTextContent("10° → 12°");
    expect(row).toHaveTextContent("coach@virginia.edu");
    expect(row).toHaveTextContent("2026-11-12");
  });

  it("us24_change_log_says_when_there_are_no_changes", async () => {
    await renderPage();
    const log = await region("Threshold changes");
    expect(within(log).getByText("No threshold changes yet.")).toBeInTheDocument();
  });

  it("us24_saving_a_threshold_refreshes_the_change_log", async () => {
    vi.mocked(api.updateFault).mockResolvedValue(fault({ threshold: 12 }));
    vi.mocked(api.thresholdChanges).mockResolvedValueOnce({ items: [] }).mockResolvedValue({ items: [CHANGE] });
    await renderPage();
    await editThreshold(0, "12");
    const log = await region("Threshold changes");
    expect(await within(log).findByText("10° → 12°")).toBeInTheDocument();
    expect(api.thresholdChanges).toHaveBeenCalledTimes(2);
  });

  it("us24_ratio_changes_are_shown_without_a_degree_sign", async () => {
    vi.mocked(api.thresholdChanges).mockResolvedValue({ items: [{ ...CHANGE, fault_id: "bar_path_drift",
      fault_name: "Bar drifts forward and back", unit: "", old_threshold: 0.25, new_threshold: 0.3 }] });
    await renderPage();
    expect(await within(await region("Threshold changes")).findByText("0.25 → 0.3")).toBeInTheDocument();
  });
});
