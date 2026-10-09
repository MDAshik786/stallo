"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { ColumnChart } from "@/components/charts";
import { SuspensionCard } from "@/components/suspension-card";
import { api, type AgentRun, type RevenueBucket } from "@/lib/api";

type Turn =
  | { kind: "seller"; text: string }
  | { kind: "agent"; text: string }
  | { kind: "chart"; result: Record<string, unknown> }
  | { kind: "run"; run: AgentRun };

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function shortLabel(label: string) {
  const [y, m, d] = label.split("-");
  if (d) return `${d} ${MONTHS[Number(m) - 1]}`;
  return `${MONTHS[Number(m) - 1]} ${y.slice(2)}`;
}

const EXAMPLES = [
  "add a rose bouquet for ₹899",
  "add a jasmine garland",
  "how did flowers do this month vs last?",
  "which products sold the most?",
];

export default function AgentPage() {
  const queryClient = useQueryClient();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  function settle(run: AgentRun) {
    setTurns((prev) => {
      const without = prev.filter((t) => !(t.kind === "run" && t.run.id === run.id));
      const next: Turn[] = [...without, { kind: "run", run }];
      if (run.reply) next.push({ kind: "agent", text: run.reply });
      const chart = (run.results ?? []).find((r) => r.tool === "query_revenue");
      if (chart) next.push({ kind: "chart", result: chart.result });
      if (run.error) next.push({ kind: "agent", text: run.error });
      return next;
    });
    // the agent writes products and audit rows; both lists are now stale
    queryClient.invalidateQueries({ queryKey: ["products"] });
    queryClient.invalidateQueries({ queryKey: ["actions"] });
  }

  const start = useMutation({
    mutationFn: (utterance: string) => api.startRun(utterance),
    onSuccess: settle,
  });

  const resume = useMutation({
    mutationFn: (v: { id: string; answer?: string; approved?: boolean }) =>
      api.resumeRun(v.id, { answer: v.answer, approved: v.approved }),
    onSuccess: settle,
  });

  const actions = useQuery({ queryKey: ["actions"], queryFn: () => api.listActions(8) });

  const busy = start.isPending || resume.isPending;

  function send(text: string) {
    setTurns((prev) => [...prev, { kind: "seller", text }]);
    setDraft("");
    start.mutate(text);
  }

  const waiting = turns.findLast(
    (t): t is Extract<Turn, { kind: "run" }> =>
      t.kind === "run" &&
      (t.run.status === "awaiting_input" || t.run.status === "awaiting_approval"),
  );

  return (
    <main className="mx-auto grid w-full max-w-5xl gap-8 px-6 py-10 lg:grid-cols-[1fr_280px]">
      <section className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight">Assistant</h1>
        <p className="mt-1 text-[13px] text-muted">
          Describe what you want. Nothing shoppers can see changes without your approval.
        </p>

        <div className="mt-6 space-y-3">
          {turns.length === 0 && (
            <div className="rounded-xl border border-dashed border-border p-6">
              <p className="text-[13px] text-muted">Try one of these:</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {EXAMPLES.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => send(example)}
                    className="rounded-lg border border-border px-3 py-1.5 text-[13px] transition-colors hover:border-accent hover:text-accent"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn, i) => {
            if (turn.kind === "seller") {
              return (
                <div key={i} className="flex justify-end">
                  <p className="max-w-[80%] rounded-2xl rounded-br-sm bg-accent px-3.5 py-2 text-[13px] text-white dark:text-black">
                    {turn.text}
                  </p>
                </div>
              );
            }
            if (turn.kind === "agent") {
              return (
                <div key={i} className="flex justify-start">
                  <p className="max-w-[80%] rounded-2xl rounded-bl-sm border border-border bg-surface px-3.5 py-2 text-[13px]">
                    {turn.text}
                  </p>
                </div>
              );
            }
            if (turn.kind === "chart") {
              const buckets = (turn.result.buckets ?? []) as RevenueBucket[];
              if (buckets.length < 2) return null;
              return (
                <div key={i} className="max-w-[92%]">
                  <ColumnChart
                    title="Revenue"
                    data={buckets.map((b) => ({
                      label: shortLabel(b.label),
                      value: b.revenue_paise,
                      sub: `${b.orders} orders`,
                    }))}
                  />
                </div>
              );
            }
            if (!turn.run.suspension) return null;
            return (
              <SuspensionCard
                key={turn.run.id}
                suspension={turn.run.suspension}
                pending={busy}
                onAnswer={(answer) => resume.mutate({ id: turn.run.id, answer })}
                onDecision={(approved) => resume.mutate({ id: turn.run.id, approved })}
              />
            );
          })}

          {busy && <p className="px-1 text-[12px] text-subtle">Thinking…</p>}
          <div ref={endRef} />
        </div>

        <form
          className="mt-6 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim() && !busy && !waiting) send(draft.trim());
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={busy || Boolean(waiting)}
            placeholder={waiting ? "Answer the question above first…" : "Tell the agent what to do…"}
            className="flex-1 rounded-lg border border-border bg-surface px-3.5 py-2.5 text-[13px] outline-none transition-colors placeholder:text-subtle focus:border-accent disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim() || Boolean(waiting)}
            className="rounded-lg bg-accent px-4 py-2.5 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40 dark:text-black"
          >
            Send
          </button>
        </form>
      </section>

      <aside className="min-w-0">
        <h2 className="text-[13px] font-medium">Activity</h2>
        <p className="mt-1 text-[12px] text-muted">Everything the agent did.</p>

        <ul className="mt-4 space-y-2">
          {actions.data?.length === 0 && <li className="text-[12px] text-subtle">Nothing yet.</li>}
          {actions.data?.map((action) => (
            <li key={action.id} className="rounded-lg border border-border bg-surface px-3 py-2">
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate font-mono text-[11px]">{action.tool}</span>
                <span className="shrink-0 text-[10px] tabular-nums text-subtle">
                  {action.duration_ms ?? 0}ms
                </span>
              </div>
              <p className="mt-0.5 truncate text-[11px] text-muted">
                {typeof action.result?.name === "string" ? action.result.name : action.status}
              </p>
              {action.undone && <p className="mt-0.5 text-[10px] text-subtle">undone</p>}
            </li>
          ))}
        </ul>
      </aside>
    </main>
  );
}
