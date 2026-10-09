"use client";

import { useState } from "react";

import type { Suspension } from "@/lib/api";

type Props = {
  suspension: Suspension;
  pending: boolean;
  onAnswer: (answer: string) => void;
  onDecision: (approved: boolean) => void;
};

/**
 * The agent paused and is waiting. Clarification and approval come from the
 * same mechanism on the server, so they render from one component — the only
 * difference is whether the seller supplies a value or a decision.
 */
export function SuspensionCard({ suspension, pending, onAnswer, onDecision }: Props) {
  const [draft, setDraft] = useState("");

  if (suspension.kind === "request_confirmation") {
    return (
      <div className="rounded-xl border border-warning/30 bg-warning-soft/60 p-4">
        <p className="text-[13px] font-medium">Needs your approval</p>
        <p className="mt-1 text-[13px] text-muted">
          {suspension.summary ?? suspension.action?.replace(/_/g, " ")}
        </p>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            disabled={pending}
            onClick={() => onDecision(true)}
            className="rounded-lg bg-accent px-3.5 py-2 text-[13px] font-medium text-white disabled:opacity-40 dark:text-black"
          >
            {pending ? "Working…" : "Approve"}
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={() => onDecision(false)}
            className="rounded-lg border border-border px-3.5 py-2 text-[13px] disabled:opacity-40"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-[13px] font-medium">{suspension.prompt ?? "I need one more thing"}</p>

      {suspension.options?.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {suspension.options.map((option) => (
            <button
              key={option.value}
              type="button"
              disabled={pending}
              onClick={() => onAnswer(option.value)}
              className="rounded-lg border border-border px-3 py-1.5 text-[13px] transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : (
        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim()) onAnswer(draft.trim());
          }}
        >
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Your answer…"
            className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-[13px] outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={pending || !draft.trim()}
            className="rounded-lg bg-accent px-3.5 py-2 text-[13px] font-medium text-white disabled:opacity-40 dark:text-black"
          >
            {pending ? "…" : "Send"}
          </button>
        </form>
      )}
    </div>
  );
}
