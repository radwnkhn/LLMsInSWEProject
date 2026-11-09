import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthForm } from "@/components/AuthForm";
import { ApiError } from "@/lib/api";
import { clearSession, getToken, isProtectedPath, setSession } from "@/lib/session";

async function fill(email: string, password: string) {
  await userEvent.type(screen.getByLabelText("Email"), email);
  await userEvent.type(screen.getByLabelText("Password"), password);
}

describe("US-01 sign up and log in", () => {
  it("us01_signup_submits_email_and_password_and_reports_success", async () => {
    const session = { access_token: "tok", user: { id: "u1", email: "a@virginia.edu", is_admin: false } };
    const submit = vi.fn().mockResolvedValue(session);
    const onSuccess = vi.fn();
    render(<AuthForm mode="signup" submit={submit} onSuccess={onSuccess} />);
    await fill("a@virginia.edu", "squat1234");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(submit).toHaveBeenCalledWith("a@virginia.edu", "squat1234");
    expect(onSuccess).toHaveBeenCalledWith(session);
  });

  it("us01_signup_password_field_requires_8_characters", () => {
    render(<AuthForm mode="signup" submit={vi.fn()} onSuccess={vi.fn()} />);
    expect(screen.getByLabelText("Password")).toHaveAttribute("minLength", "8");
    expect(screen.getByLabelText("Email")).toHaveAttribute("type", "email");
  });

  it("us01_wrong_password_shows_message_and_does_not_log_in", async () => {
    const submit = vi.fn().mockRejectedValue(new ApiError(401, "Incorrect email or password"));
    const onSuccess = vi.fn();
    render(<AuthForm mode="login" submit={submit} onSuccess={onSuccess} />);
    await fill("a@virginia.edu", "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
    expect(onSuccess).not.toHaveBeenCalled();
    expect(getToken()).toBeNull();
  });

  it("us01_network_failure_shows_a_generic_error", async () => {
    const submit = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    render(<AuthForm mode="login" submit={submit} onSuccess={vi.fn()} />);
    await fill("a@virginia.edu", "squat1234");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong. Please try again.");
  });

  it("us01_session_is_stored_in_a_cookie_and_cleared_on_logout", () => {
    setSession("tok-123");
    expect(getToken()).toBe("tok-123");
    expect(document.cookie).toContain("alibi_session=tok-123");
    clearSession();
    expect(getToken()).toBeNull();
  });

  it("us01_history_upload_results_and_admin_pages_need_login", () => {
    for (const path of ["/history", "/upload", "/results/abc", "/admin", "/admin/analyses/abc"]) {
      expect(isProtectedPath(path)).toBe(true);
    }
    for (const path of ["/login", "/signup", "/status", "/"]) {
      expect(isProtectedPath(path)).toBe(false);
    }
  });
});
