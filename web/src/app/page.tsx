import Link from "next/link";

const PILLARS = [
  {
    title: "It asks instead of guessing",
    body: "Say “add a jasmine garland” with no price and it stops and asks. Values it cannot trace back to what you typed are never saved — a model that invents a confident ₹1,500 is worse than one that asks.",
  },
  {
    title: "Nothing goes live without you",
    body: "Publishing and deleting are not in the model's vocabulary at all. They run only on an approval you click, so no amount of typed “yes” can reach a write.",
  },
  {
    title: "Everything it did, on the record",
    body: "Every action is appended to an audit log with its arguments, result and inverse. The activity timeline and undo are both just reads of that log.",
  },
];

const SCORES = [
  { label: "baseline", tools: "59.5%", args: "92.0%", safety: "4" },
  { label: "longer system prompt", tools: "57.1%", args: "87.5%", safety: "5" },
  { label: "+ deterministic guards", tools: "69.0%", args: "93.1%", safety: "1" },
  { label: "+ grounding", tools: "76.2%", args: "93.8%", safety: "0" },
];

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-16 sm:py-24">
      <section className="max-w-2xl">
        <p className="text-[12px] font-medium uppercase tracking-widest text-accent">
          AI-native commerce
        </p>
        <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
          Run your store by describing what you want.
        </h1>
        <p className="mt-4 text-[15px] leading-relaxed text-muted">
          Small sellers know their products. They don&apos;t know software. Stallo replaces the
          twelve-field product form with a sentence, and the dashboard with a question — while
          keeping every change behind your approval.
        </p>

        <div className="mt-7 flex flex-wrap gap-3">
          <Link
            href="/agent"
            className="rounded-lg bg-accent px-4 py-2.5 text-[13px] font-medium text-white transition-opacity hover:opacity-90 dark:text-black"
          >
            Open the assistant
          </Link>
          <Link
            href="/products"
            className="rounded-lg border border-border px-4 py-2.5 text-[13px] font-medium transition-colors hover:border-accent hover:text-accent"
          >
            Browse the catalogue
          </Link>
        </div>
      </section>

      <section className="mt-14 overflow-hidden rounded-2xl border border-border bg-surface">
        <div className="flex items-center gap-2 border-b border-border px-5 py-3">
          <span className="h-2 w-2 rounded-full bg-series-1" />
          <p className="text-[12px] text-muted">A conversation with the store</p>
        </div>

        <div className="space-y-3 p-5">
          <Said>add a jasmine garland</Said>
          <Replied>What price should I set?</Replied>
          <Said>₹340</Said>
          <Replied>Created “Jasmine Garland” as a draft.</Replied>
          <Said>how did flowers do this month vs last?</Said>
          <Replied>
            ₹45,067 from flowers across 28 orders, 2026-09-01 to 2026-10-09. That is down 16.4% on
            the previous period (₹53,894).
          </Replied>
          <Said>publish it</Said>
          <Replied approval>
            This will publish Jasmine Garland so shoppers can see it. Approve?
          </Replied>
        </div>
      </section>

      <section className="mt-14 grid gap-4 sm:grid-cols-3">
        {PILLARS.map((pillar) => (
          <div key={pillar.title} className="rounded-xl border border-border bg-surface p-5">
            <h2 className="text-[14px] font-medium">{pillar.title}</h2>
            <p className="mt-2 text-[13px] leading-relaxed text-muted">{pillar.body}</p>
          </div>
        ))}
      </section>

      <section className="mt-14">
        <h2 className="text-[15px] font-semibold tracking-tight">Measured, not asserted</h2>
        <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-muted">
          The agent is regression-tested against 42 cases scoring tool selection, argument accuracy
          and safety separately. Twelve are adversarial — ambiguous pronouns, prompt injection inside
          a product description, cross-tenant probes, and chit-chat that must call no tool.
        </p>

        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[460px] border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border text-left text-[12px] text-muted">
                <th className="py-2 pr-4 font-medium">Change</th>
                <th className="py-2 pr-4 font-medium">Tool selection</th>
                <th className="py-2 pr-4 font-medium">Arguments</th>
                <th className="py-2 font-medium">Safety violations</th>
              </tr>
            </thead>
            <tbody>
              {SCORES.map((row, i) => {
                const best = i === SCORES.length - 1;
                return (
                  <tr key={row.label} className="border-b border-border last:border-0">
                    <td className={`py-2 pr-4 ${best ? "font-medium" : "text-muted"}`}>
                      {row.label}
                    </td>
                    <td className={`py-2 pr-4 tabular-nums ${best ? "font-medium" : ""}`}>
                      {row.tools}
                    </td>
                    <td className={`py-2 pr-4 tabular-nums ${best ? "font-medium" : ""}`}>
                      {row.args}
                    </td>
                    <td
                      className={`py-2 tabular-nums ${
                        row.safety === "0" ? "font-medium text-success" : "text-warning"
                      }`}
                    >
                      {row.safety}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <p className="mt-4 max-w-2xl text-[13px] leading-relaxed text-muted">
          A longer, more carefully written system prompt scored{" "}
          <span className="text-foreground">worse</span>. That result is why invariants live in a
          guard layer in code rather than as instructions in a prompt.
        </p>
      </section>

      <footer className="mt-16 border-t border-border pt-6">
        <p className="text-[12px] leading-relaxed text-muted">
          In development. Authentication is a stub and the assistant runs on a local model, so it is
          unavailable in the hosted demo — the catalogue, orders and analytics all work here.{" "}
          <a
            href="https://github.com/MDAshik786/stallo"
            className="text-accent hover:underline"
            target="_blank"
            rel="noreferrer"
          >
            Source on GitHub
          </a>
          .
        </p>
      </footer>
    </main>
  );
}

function Said({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[78%] rounded-2xl rounded-br-sm bg-accent px-3.5 py-2 text-[13px] text-white dark:text-black">
        {children}
      </p>
    </div>
  );
}

function Replied({ children, approval }: { children: React.ReactNode; approval?: boolean }) {
  return (
    <div className="flex justify-start">
      <div
        className={`max-w-[78%] rounded-2xl rounded-bl-sm px-3.5 py-2 text-[13px] ${
          approval
            ? "border border-warning/30 bg-warning-soft/60"
            : "border border-border bg-background"
        }`}
      >
        {children}
        {approval && (
          <span className="mt-2 flex gap-2">
            <span className="rounded-md bg-accent px-2.5 py-1 text-[11px] font-medium text-white dark:text-black">
              Approve
            </span>
            <span className="rounded-md border border-border px-2.5 py-1 text-[11px]">Cancel</span>
          </span>
        )}
      </div>
    </div>
  );
}
