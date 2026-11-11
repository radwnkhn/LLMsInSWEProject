import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentType } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "@/lib/api";
import type { AdminFault, AdminFaultLift } from "@/lib/types";

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, adminFaults: vi.fn(), updateFault: vi.fn(), addFault: vi.fn() } };
});

// Loaded at run time so each test reports its own failure while the page doesn't exist yet.
const PAGE = "@/app/admin/faults/page";
async function renderPage() {
  const { default: Page } = (await import(/* @vite-ignore */ PAGE)) as { default: ComponentType };
  render(<Page />);
}

const fault = (overrides: Partial<AdminFault>): AdminFault => ({
  lift: "squat", id: "knee_cave", name: "Knees cave inward", short_name: "knee cave", category: "safety", safety: true,
  metric: "knee_valgus_deg", metric_label: "valgus", threshold: 10, direction: "above", unit: "°", enabled: true,
  ...overrides,
});

const LIFTS: AdminFaultLift[] = [
  { lift: "squat", lift_label: "Squat",
    faults: [fault({}), fault({ id: "hips_rise_early", name: "Hips rise before your shoulders", short_name: "hips rising early",
      category: "technique", safety: false, metric: "torso_lean_increase_deg", metric_label: "torso lean increase" })],
    metrics: [{ metric: "knee_angle_min_deg", label: "knee angle at the bottom", unit: "°" },
      { metric: "knee_valgus_deg", label: "valgus", unit: "°" }] },
  { lift: "bench_press", lift_label: "Bench Press",
    faults: [fault({ lift: "bench_press", id: "elbow_flare", name: "Elbows flare out too wide", short_name: "elbow flare",
      metric: "elbow_flare_deg", metric_label: "elbow flare", enabled: false })],
    metrics: [{ metric: "elbow_angle_min_deg", label: "elbow angle at the bottom", unit: "°" }] },
];

function region(name: string) {
  return screen.findByRole("region", { name });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.adminFaults).mockResolvedValue({ lifts: structuredClone(LIFTS) });
});

describe("US-25 fault list page", () => {
  it("us25_lists_every_fault_per_lift_with_category_safety_measurement_and_status", async () => {
    await renderPage();
    const squat = await region("Squat faults");
    const rows = within(squat).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("Knees cave inward")).toBeInTheDocument();
    expect(rows[0]).toHaveTextContent("Safety");
    expect(rows[0]).toHaveTextContent("Yes");
    expect(rows[0]).toHaveTextContent("valgus");
    expect(rows[0]).toHaveTextContent("Enabled");
    expect(rows[1]).toHaveTextContent("Technique");
    expect(rows[1]).toHaveTextContent("No");
    const bench = await region("Bench Press faults");
    expect(within(bench).getAllByRole("row")[1]).toHaveTextContent("Disabled");
  });

  it("us25_editing_saves_the_display_name_and_short_description", async () => {
    vi.mocked(api.updateFault).mockResolvedValue(fault({ name: "Knees collapse inward", short_name: "knee collapse" }));
    await renderPage();
    const squat = await region("Squat faults");
    await userEvent.click(within(squat).getAllByRole("button", { name: "Edit" })[0]);
    const name = within(squat).getByLabelText("Display name");
    await userEvent.clear(name);
    await userEvent.type(name, "Knees collapse inward");
    const short = within(squat).getByLabelText("Short description");
    await userEvent.clear(short);
    await userEvent.type(short, "knee collapse");
    await userEvent.click(within(squat).getByRole("button", { name: "Save" }));
    expect(api.updateFault).toHaveBeenCalledWith("squat", "knee_cave",
      { name: "Knees collapse inward", short_name: "knee collapse" }, null);
    expect(await within(squat).findByText("Knees collapse inward")).toBeInTheDocument();
    expect(within(squat).queryByLabelText("Display name")).not.toBeInTheDocument();
  });

  it("us25_blank_or_too_long_names_are_rejected_before_saving", async () => {
    await renderPage();
    const squat = await region("Squat faults");
    await userEvent.click(within(squat).getAllByRole("button", { name: "Edit" })[0]);
    await userEvent.clear(within(squat).getByLabelText("Display name"));
    await userEvent.click(within(squat).getByRole("button", { name: "Save" }));
    expect(await within(squat).findByRole("alert")).toHaveTextContent("Display name is required");
    await userEvent.type(within(squat).getByLabelText("Display name"), "x".repeat(81));
    await userEvent.click(within(squat).getByRole("button", { name: "Save" }));
    expect(await within(squat).findByRole("alert")).toHaveTextContent("80 characters or fewer");
    expect(api.updateFault).not.toHaveBeenCalled();
  });

  it("us25_disable_and_enable_switch_the_fault_status", async () => {
    vi.mocked(api.updateFault)
      .mockResolvedValueOnce(fault({ enabled: false }))
      .mockResolvedValueOnce(fault({ enabled: true }));
    await renderPage();
    const squat = await region("Squat faults");
    const row = () => within(squat).getAllByRole("row")[1];
    await userEvent.click(within(row()).getByRole("button", { name: "Disable" }));
    expect(api.updateFault).toHaveBeenLastCalledWith("squat", "knee_cave", { enabled: false }, null);
    expect(await within(squat).findByText("Disabled")).toBeInTheDocument();
    await userEvent.click(within(row()).getByRole("button", { name: "Enable" }));
    expect(api.updateFault).toHaveBeenLastCalledWith("squat", "knee_cave", { enabled: true }, null);
    expect(await within(row()).findByText("Enabled")).toBeInTheDocument();
  });

  it("us25_add_form_offers_only_measurements_the_lift_already_computes", async () => {
    await renderPage();
    const form = await region("Add a fault");
    const measurement = within(form).getByLabelText("Measurement");
    expect(measurement.tagName).toBe("SELECT");
    expect(within(measurement).getAllByRole("option").map((o) => o.textContent))
      .toEqual(["knee angle at the bottom", "valgus"]);
    await userEvent.selectOptions(within(form).getByLabelText("Lift"), "bench_press");
    expect(within(within(form).getByLabelText("Measurement")).getAllByRole("option").map((o) => o.textContent))
      .toEqual(["elbow angle at the bottom"]);
  });

  it("us25_adding_a_fault_sends_it_and_lists_it_under_its_lift", async () => {
    const added = fault({ id: "knees_stay_bent", name: "Knees stay bent", short_name: "knee bend", category: "technique",
      safety: false, metric: "knee_angle_min_deg", metric_label: "knee angle at the bottom", threshold: 179, direction: "below" });
    vi.mocked(api.addFault).mockResolvedValue(added);
    await renderPage();
    const form = await region("Add a fault");
    await userEvent.type(within(form).getByLabelText("Fault ID"), "knees_stay_bent");
    await userEvent.type(within(form).getByLabelText("Display name"), "Knees stay bent");
    await userEvent.type(within(form).getByLabelText("Short description"), "knee bend");
    await userEvent.selectOptions(within(form).getByLabelText("Flag when the measurement is"), "below");
    await userEvent.type(within(form).getByLabelText("Threshold"), "179");
    await userEvent.click(within(form).getByRole("button", { name: "Add fault" }));
    expect(api.addFault).toHaveBeenCalledWith({ lift: "squat", id: "knees_stay_bent", name: "Knees stay bent",
      short_name: "knee bend", category: "technique", metric: "knee_angle_min_deg", threshold: 179, direction: "below" }, null);
    const squat = await region("Squat faults");
    expect(await within(squat).findByText("Knees stay bent")).toBeInTheDocument();
  });

  it("us25_rejected_additions_show_the_reason", async () => {
    vi.mocked(api.addFault).mockRejectedValue(new ApiError(409, "squat already has a fault with ID 'knee_cave'"));
    await renderPage();
    const form = await region("Add a fault");
    await userEvent.type(within(form).getByLabelText("Fault ID"), "knee_cave");
    await userEvent.type(within(form).getByLabelText("Display name"), "Knees cave");
    await userEvent.type(within(form).getByLabelText("Short description"), "knee cave");
    await userEvent.type(within(form).getByLabelText("Threshold"), "5");
    await userEvent.click(within(form).getByRole("button", { name: "Add fault" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("already has a fault with ID 'knee_cave'");
  });

  it("us25_non_admins_see_admins_only", async () => {
    vi.mocked(api.adminFaults).mockRejectedValue(new ApiError(403, "Admins only"));
    await renderPage();
    expect(await screen.findByRole("heading", { name: "403: Admins only" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Add a fault" })).not.toBeInTheDocument();
  });

  it("us25_admin_analyses_page_links_to_the_fault_list", async () => {
    const { default: AdminPage } = await import("@/app/admin/page");
    vi.spyOn(api, "adminAnalyses").mockResolvedValue({ items: [] });
    vi.spyOn(api, "adminErrors").mockResolvedValue({ counts: {} });
    render(<AdminPage />);
    expect(await screen.findByRole("link", { name: "Fault list" })).toHaveAttribute("href", "/admin/faults");
  });
});
