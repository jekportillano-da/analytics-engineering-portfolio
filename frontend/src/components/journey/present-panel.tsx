"use client";

import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ExecutiveInsight } from "@/lib/presentation/contract-loader";

type Domain = "people" | "wage" | "platform";
const labels: Record<Domain, string> = { people: "People", wage: "Wage", platform: "Trust" };
const money = new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP", maximumFractionDigits: 0 });

function formatEvidence(value: string | number, metricId: string | null) {
  if (typeof value !== "number") return value;
  if (metricId === "people.attrition_rate") return `${(value * 100).toFixed(2)}%`;
  if (metricId?.startsWith("wage.")) return money.format(value);
  return value.toLocaleString();
}

function EvidenceDrawer({ insight }: { insight: ExecutiveInsight }) {
  return <Dialog.Root><Dialog.Trigger className="trace-insight" type="button">Trace this insight</Dialog.Trigger><Dialog.Portal><Dialog.Overlay className="technical-drawer-overlay" /><Dialog.Content className="technical-drawer"><div className="drawer-heading"><div><Dialog.Title>Evidence trace</Dialog.Title><Dialog.Description>Resolved references supporting this executive observation.</Dialog.Description></div><Dialog.Close aria-label="Close evidence trace" className="drawer-close" type="button">Close</Dialog.Close></div><div className="evidence-list">{insight.evidence.map((evidence, index) => <article key={`${evidence.artifact_id}-${index}`}><p>{evidence.artifact_id}</p><strong>{evidence.field}: {formatEvidence(evidence.observed_value, evidence.metric_id)}</strong><span>{evidence.governed_source}</span><small>{evidence.collection}{evidence.record_id ? ` · ${evidence.record_id}` : ""}{evidence.metric_id ? ` · ${evidence.metric_id}` : ""}</small></article>)}</div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}

export function PresentPanel({ insights }: { insights: ExecutiveInsight[] }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const requestedDomain = searchParams.get("domain");
  const requestedQuestion = searchParams.get("question");
  const requestedInsight = insights.find((insight) => insight.question_id === requestedQuestion);
  const domain: Domain = requestedInsight?.domain ?? (requestedDomain === "people" || requestedDomain === "wage" || requestedDomain === "platform" ? requestedDomain : "people");
  const byDomain = insights.filter((insight) => insight.domain === domain);
  const selected = requestedInsight?.domain === domain ? requestedInsight : byDomain[0];
  const questions = Object.fromEntries(insights.map((insight) => [insight.question_id, insight]));
  const selectInsight = (insight: ExecutiveInsight) => router.replace(`${pathname}?domain=${insight.domain}&question=${encodeURIComponent(insight.question_id)}`, { scroll: false });
  const changeDomain = (next: Domain) => selectInsight(insights.find((insight) => insight.domain === next)!);
  return <main className="journey-panel present-panel" id="main-content" tabIndex={-1}><p className="panel-stage-number">STAGE 06</p><h1 className="panel-title">PRESENT</h1><p className="journey-lede">Executive briefing.</p><p className="journey-intro">Governed evidence, distilled for leadership.</p><div className="briefing-tabs" role="tablist" aria-label="Executive briefing category">{(["people", "wage", "platform"] as const).map((item) => <button aria-selected={domain === item} key={item} onClick={() => changeDomain(item)} role="tab" type="button">{labels[item]}</button>)}</div><section className="briefing-layout"><aside className="briefing-questions" aria-label="Executive questions">{byDomain.map((insight) => <button aria-current={selected.insight_id === insight.insight_id ? "true" : undefined} key={insight.insight_id} onClick={() => selectInsight(insight)} type="button">{insight.executive_question}</button>)}</aside><article className="executive-finding"><p className="eyebrow">EXECUTIVE QUESTION</p><h2>{selected.executive_question}</h2><p className="finding-headline">{selected.headline}</p><div className="finding-evidence"><p>KEY EVIDENCE</p>{selected.evidence.slice(0, 3).map((evidence, index) => <span key={index}>{formatEvidence(evidence.observed_value, evidence.metric_id)}</span>)}<small>{selected.evidence_state.replaceAll("_", " ")}</small></div><p className="finding-narrative">{selected.narrative}</p><div className="knowledge-split"><div><p>WHAT THE EVIDENCE SHOWS</p><span>{selected.narrative}</span></div><div><p>WHAT THE DATA DOES NOT ESTABLISH</p><ul>{selected.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></div></div><div className="next-questions"><p>INVESTIGATE NEXT</p>{selected.next_question_ids.length ? selected.next_question_ids.map((id) => <button key={id} onClick={() => selectInsight(questions[id])} type="button">{questions[id].executive_question} <span aria-hidden="true">→</span></button>) : <span>No further question is declared by this insight.</span>}</div><div className="briefing-actions"><EvidenceDrawer insight={selected} /><Link href="/insight">View underlying analysis →</Link><Link href="/model">Trace metric model →</Link><Link href="/govern">Inspect governance →</Link><Link href="/source">View source context →</Link></div></article></section><footer className="journey-handoff present-payoff"><p>Executive reporting is the final consumption layer of the same governed system: SOURCE → INGEST → MODEL → GOVERN → INSIGHT → PRESENT.</p></footer></main>;
}