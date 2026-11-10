"use client";

import { PageTitle } from "@/components/AppShell";
import { Card, Note } from "@/components/ui";

const STATUSES: [string, string][] = [
  ["ok", "The answer was exactly the expected value (structured JSON or a bare number/decision)."],
  ["extracted", "The value was the only candidate in a longer answer. Valid, but flagged."],
  ["truncated", "The output-token limit cut the answer (often because reasoning used the budget). No value."],
  ["empty", "The visible answer was empty. No value."],
  ["unparsable / ambiguous", "No value, or more than one candidate value, in the text. No value — the first number is never taken."],
  ["out_of_range", "A number outside the 1–7 scale. Not clamped. No value."],
  ["refused", "Blocked by the provider's safety system. No value."],
  ["error", "Network, HTTP or provider error after the allowed retries. No value; can be retried with Resume."],
  ["skipped", "The record has neither title nor abstract."],
];

export default function Guide() {
  return (
    <>
      <PageTitle title="Guide" subtitle="What BibAIFilter does, what it records and how to report it." />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Two tasks">
          <p className="text-[13.5px] leading-relaxed"><b>Relevance score (1–7).</b> Ranks records by how relevant they are to a topic, which can be a whole research question rather than a keyword. Useful to order a large set so that the most relevant records are read first.</p>
          <p className="mt-2 text-[13.5px] leading-relaxed"><b>Eligibility screening.</b> Applies explicit inclusion and exclusion criteria to title and abstract and answers include, exclude or uncertain with a reason. “Uncertain” keeps the record, because missing a relevant study is worse than reading an irrelevant one.</p>
          <p className="mt-2 text-[13.5px] leading-relaxed">If your file has an include/exclude column, recall, precision, ROC AUC and work saved over sampling (WSS@95) are computed, next to a BM25 keyword baseline on the same records.</p>
        </Card>
        <Card title="What is logged for every call">
          <ul className="list-disc space-y-1 pl-5 text-[13.5px]">
            <li>requested model and the model named in the provider's response (mismatches flagged)</li>
            <li>the parameters actually sent — e.g. “temperature: not sent (model rejects temperature)”</li>
            <li>every HTTP attempt with status and waiting time; at most 5 attempts, only for rate limits, server errors and timeouts</li>
            <li>finish reason, raw answer, parse status, tokens (including reasoning tokens), latency and estimated cost</li>
            <li>the prompt's SHA-256 and the record's content hash; the run manifest stores tool, Python and package versions and the input file's SHA-256</li>
          </ul>
        </Card>
        <Card title="Answer statuses">
          <table className="data"><tbody>{STATUSES.map(([k, v]) => <tr key={k}><td className="font-semibold">{k}</td><td>{v}</td></tr>)}</tbody></table>
        </Card>
        <Card title="Good practice">
          <ul className="list-disc space-y-1 pl-5 text-[13.5px]">
            <li>Run a small trial first (“only the first N records”) and read the call log.</li>
            <li>Use at least 3 repetitions to see how stable the answers are.</li>
            <li>For reasoning models, set a low reasoning level for scoring, or keep a generous token limit — limits include reasoning tokens.</li>
            <li>Report the run manifest (model id, served model, parameters sent, prompt hash, dates) in your methods section.</li>
            <li>Use LLM output to prioritise and support human screening, not to replace it.</li>
          </ul>
        </Card>
        <Card title="Privacy">
          <p className="text-[13.5px] leading-relaxed">Each call sends the record's title, abstract and keywords to the selected provider. Check the provider's data-use terms and the licence of your database. Free tiers may use inputs for training. With Ollama, nothing leaves your computer. API keys are stored locally and never written to run files.</p>
        </Card>
        <Card title="Where your work is saved">
          <p className="text-[13.5px] leading-relaxed">Everything lives in your <b>workspace folder</b> (default <code>~/BibAIFilter</code>, change it under Settings): uploaded files in <code>datasets/</code>, one folder per run in <code>runs/</code> with the manifest and the full call log, and finished results in <code>exports/</code> — or in the folder you chose when starting the run. Back up or share the run folder to let others check your results.</p>
        </Card>
        <Card title="Command line">
          <pre className="whitespace-pre-wrap rounded-lg bg-bg p-3 text-[12px]">{`bibaifilter                  # open this interface
bibaifilter run spec.json    # same run without the interface (scriptable)
bibaifilter models           # model catalogue and parameter rules
bibaifilter check openai gpt-6-luna   # one test call
bibaifilter baseline file.xlsx --query "topic" --label-col included`}</pre>
        </Card>
      </div>
    </>
  );
}
