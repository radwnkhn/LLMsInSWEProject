import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DeleteAccountForm } from "@/components/DeleteAccountForm";
import { HistoryList } from "@/components/HistoryList";
import { ApiError } from "@/lib/api";
import { isProtectedPath } from "@/lib/session";
import type { HistoryItem } from "@/lib/types";

const item: HistoryItem = { analysis_id: "analysis-1", upload_id: "upload-1", created_at: "2026-11-09T12:00:00Z",
  lift: "squat", lift_label: "Squat", rep_count: 5, top_fix_title: null,
  status: "done", final_status: "passed_first_try", status_label: "Analyzed" };

describe("US-21 upload deletion", () => {
  it("us21_upload_delete_requires_confirmation_and_cancel_preserves_the_upload", async () => {
    const onDelete = vi.fn();
    render(<HistoryList items={[item]} onDelete={onDelete} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete upload" }));
    const dialog = screen.getByRole("dialog", { name: "Delete this upload?" });
    expect(dialog).toHaveTextContent("video, frames, measurements and AI feedback");
    expect(onDelete).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("us21_confirmation_deletes_the_upload_id_including_its_analysis_retries", async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<HistoryList items={[item]} onDelete={onDelete} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete upload" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete upload" }));
    expect(onDelete).toHaveBeenCalledWith("upload-1");
  });

  it("us21_escape_cancels_and_returns_focus_to_the_delete_trigger", async () => {
    render(<HistoryList items={[item]} onDelete={vi.fn()} />);
    const trigger = screen.getByRole("button", { name: "Delete upload" });
    await userEvent.click(trigger);
    expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete upload" })).toHaveFocus();
    await userEvent.tab();
    expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("us21_pending_deletion_blocks_duplicate_confirmation", async () => {
    const onDelete = vi.fn().mockReturnValue(new Promise(() => {}));
    render(<HistoryList items={[item]} onDelete={onDelete} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete upload" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete upload" }));
    expect(screen.getByRole("button", { name: "Deleting…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it("us21_failed_cleanup_remains_retryable_without_claiming_success", async () => {
    const onDelete = vi.fn().mockRejectedValueOnce(new ApiError(502, "Couldn't delete the video. Please try again.")).mockResolvedValue(undefined);
    render(<HistoryList items={[item]} onDelete={onDelete} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete upload" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete upload" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Couldn't delete the video");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete upload" }));
    expect(onDelete).toHaveBeenCalledTimes(2);
  });

  it("us21_deleted_entries_cannot_remain_selected_for_comparison", async () => {
    const second = { ...item, upload_id: "upload-2", analysis_id: "analysis-2" };
    const { rerender } = render(<HistoryList items={[item, second]} onDelete={vi.fn()} />);
    await userEvent.click(screen.getAllByRole("checkbox")[0]);
    await userEvent.click(screen.getAllByRole("checkbox")[1]);
    rerender(<HistoryList items={[second]} onDelete={vi.fn()} />);
    expect(screen.queryByRole("link", { name: "Compare selected uploads" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Compare selected uploads" })).toBeDisabled();
  });
});

describe("US-21 account deletion", () => {
  it("us21_account_delete_has_a_separate_confirmation_explaining_what_is_removed", async () => {
    const remove = vi.fn();
    render(<DeleteAccountForm deleteAccount={remove} onDeleted={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete account" }));
    const dialog = screen.getByRole("dialog", { name: "Delete your account?" });
    expect(dialog).toHaveTextContent("all your uploads");
    expect(dialog).toHaveTextContent("cannot be undone");
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(remove).not.toHaveBeenCalled();
  });

  it("us21_the_session_is_cleared_only_after_successful_account_deletion", async () => {
    let finish: () => void = () => {};
    const remove = vi.fn().mockReturnValue(new Promise<void>((resolve) => { finish = resolve; }));
    const onDeleted = vi.fn();
    render(<DeleteAccountForm deleteAccount={remove} onDeleted={onDeleted} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete account" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete account" }));
    expect(onDeleted).not.toHaveBeenCalled();
    await act(async () => { finish(); });
    expect(onDeleted).toHaveBeenCalledOnce();
  });

  it("us21_account_deletion_failure_does_not_sign_the_user_out", async () => {
    const onDeleted = vi.fn();
    render(<DeleteAccountForm deleteAccount={vi.fn().mockRejectedValue(new ApiError(409, "Wait for analyses to finish"))} onDeleted={onDeleted} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete account" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete account" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Wait for analyses to finish");
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it("us21_settings_requires_a_session", () => {
    expect(isProtectedPath("/settings")).toBe(true);
  });
});
