"use client";

import Link from "next/link";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MetricDefinition, PeopleInsightData, WageInsightData } from "@/lib/presentation/contract-loader";

type Domain = "people" | "wage";
type PeopleView = "headcount" | "movement" | "attrition";
type WageView = "industry" | "regional" | "benchmark";

const money = new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP", maximumFractionDigits: 0 });
const month = new Intl.DateTimeFormat("en", { month: "short", year: "2-digit", timeZone: "UTC" });

function ChartTooltip({ active, payload, label, kind }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string; kind: "people" | "wage" }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>{kind === "people" ? month.format(new Date(`${label}T00:00:00Z`)) : label}</strong>{payload.map((item) => <span key={item.name}><i style={{ background: item.color }} />{item.name}: {kind === "wage" ? money.format(item.value) : item.name === "Attrition Rate" ? `${(item.value * 100).toFixed(2)}%` : item.value.toLocaleString()}</span>)}</div>;
}

function MetricContext({ definition }: { definition: MetricDefinition }) {
  return <aside className="metric-context"><p>GOVERNED METRIC CONTEXT</p><strong>{definition.metric_id}</strong><span>{definition.definition}</span><small>{definition.time_grain ? `${definition.time_grain} grain · ` : ""}{definition.aggregation_behavior.replaceAll("_", " ")}</small><details><summary>View definition and limitation</summary><p>{definition.limitations}</p></details></aside>;
}

function DataView({ rows, columns }: { rows: Record<string, string | number>[]; columns: { key: string; label: string; format?: (value: string | number) => string }[] }) {
  return <details className="data-view"><summary>View data</summary><div><table><thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${row[columns[0].key]}-${index}`}>{columns.map((column) => <td key={column.key}>{column.format ? column.format(row[column.key]) : row[column.key]}</td>)}</tr>)}</tbody></table></div></details>;
}

function PeopleWorkspace({ data }: { data: PeopleInsightData }) {
  const [view, setView] = useState<PeopleView>("headcount");
  const definitions = Object.fromEntries(data.definitions.map((definition) => [definition.metric_id, definition]));
  const viewMeta = { headcount: ["Ending Headcount", "people.ending_headcount"], movement: ["Hires vs Separations", "people.hires"], attrition: ["Attrition Rate", "people.attrition_rate"] } as const;
  const [title, definitionId] = viewMeta[view];
  const chart = view === "headcount" ? <LineChart data={data.monthly}><CartesianGrid stroke="#26323e" vertical={false} /><XAxis dataKey="period_start" minTickGap={28} tickFormatter={(value) => month.format(new Date(`${value}T00:00:00Z`))} /><YAxis width={44} /><Tooltip content={<ChartTooltip kind="people" />} /><Line dataKey="ending_headcount" dot={false} name="Ending Headcount" stroke="#55c3c6" strokeWidth={2} type="linear" /></LineChart> : view === "movement" ? <BarChart data={data.monthly}><CartesianGrid stroke="#26323e" vertical={false} /><XAxis dataKey="period_start" minTickGap={28} tickFormatter={(value) => month.format(new Date(`${value}T00:00:00Z`))} /><YAxis width={34} /><Tooltip content={<ChartTooltip kind="people" />} /><Bar dataKey="hires" fill="#55c3c6" name="Hires" /><Bar dataKey="separations" fill="#91a0ac" name="Separations" /></BarChart> : <LineChart data={data.monthly}><CartesianGrid stroke="#26323e" vertical={false} /><XAxis dataKey="period_start" minTickGap={28} tickFormatter={(value) => month.format(new Date(`${value}T00:00:00Z`))} /><YAxis tickFormatter={(value) => `${(value * 100).toFixed(0)}%`} width={42} /><Tooltip content={<ChartTooltip kind="people" />} /><Line dataKey="attrition_rate" dot={false} name="Attrition Rate" stroke="#55c3c6" strokeWidth={2} type="linear" /></LineChart>;
  const columns = view === "movement" ? [{ key: "period_start", label: "Period", format: (value: string | number) => month.format(new Date(`${value}T00:00:00Z`)) }, { key: "hires", label: "Hires" }, { key: "separations", label: "Separations" }] : [{ key: "period_start", label: "Period", format: (value: string | number) => month.format(new Date(`${value}T00:00:00Z`)) }, { key: view === "headcount" ? "ending_headcount" : "attrition_rate", label: title, format: view === "attrition" ? (value: string | number) => `${(Number(value) * 100).toFixed(2)}%` : undefined }];
  return <section className="insight-workspace"><div className="workspace-heading"><div><p className="eyebrow">GOVERNED PEOPLE MARTS</p><h2>{title}</h2><span>36 monthly periods · 2023–2025 analysis window</span></div><div className="workspace-tabs" role="tablist" aria-label="People analytical views">{(["headcount", "movement", "attrition"] as const).map((item) => <button aria-selected={view === item} key={item} onClick={() => setView(item)} role="tab" type="button">{viewMeta[item][0]}</button>)}</div></div><div className="chart-frame" aria-label={`${title} chart`}><ResponsiveContainer height="100%" width="100%">{chart}</ResponsiveContainer></div><DataView columns={columns} rows={data.monthly} /><MetricContext definition={definitions[definitionId]} /></section>;
}

function WageWorkspace({ data }: { data: WageInsightData }) {
  const [view, setView] = useState<WageView>("industry");
  const [measure, setMeasure] = useState<"average_monthly_basic_pay" | "average_monthly_allowance" | "average_monthly_wage_rate">("average_monthly_wage_rate");
  const [occupation, setOccupation] = useState("General Office Clerks");
  const [sex, setSex] = useState("Both Sexes");
  const measures = { average_monthly_basic_pay: "Basic Pay", average_monthly_allowance: "Allowance", average_monthly_wage_rate: "Wage Rate" } as const;
  const benchmarkOccupations = [...new Set(data.benchmark_occupations.map((row) => row.benchmark_occupation_name!))];
  const sexes = [...new Set(data.benchmark_occupations.filter((row) => row.benchmark_occupation_name === occupation).map((row) => row.sex!))];
  const baseRows = view === "industry" ? data.industry : view === "regional" ? data.regional : data.benchmark_occupations.filter((row) => row.benchmark_occupation_name === occupation && row.sex === sex);
  const field = view === "benchmark" ? "average_monthly_wage_rate" : measure;
  const labelField = view === "industry" ? "industry_name" : view === "regional" ? "region_name" : "industry_name";
  const rows = [...baseRows].sort((left, right) => Number(right[field] ?? 0) - Number(left[field] ?? 0));
  const chartData = rows.map((row) => ({ label: row[labelField]!, value: Number(row[field] ?? 0) }));
  const definitions = Object.fromEntries(data.definitions.map((definition) => [definition.metric_id, definition]));
  const definition = view === "benchmark" ? definitions["wage.benchmark_occupation_wage_rate"] : definitions[measure === "average_monthly_basic_pay" ? "wage.basic_pay" : measure === "average_monthly_allowance" ? "wage.allowance" : "wage.wage_rate"];
  return <section className="insight-workspace"><div className="workspace-heading"><div><p className="eyebrow">GOVERNED WAGE MARTS</p><h2>{view === "industry" ? "Industry comparison" : view === "regional" ? "Regional comparison" : "Benchmark occupation records"}</h2><span>2024 PSA OWS · published source-grain values</span></div><div className="workspace-tabs" role="tablist" aria-label="Wage analytical views">{(["industry", "regional", "benchmark"] as const).map((item) => <button aria-selected={view === item} key={item} onClick={() => setView(item)} role="tab" type="button">{item === "benchmark" ? "Benchmark Occupation" : item === "industry" ? "Industry" : "Region"}</button>)}</div></div><div className="wage-controls">{view !== "benchmark" && <label>Measure<select onChange={(event) => setMeasure(event.target.value as typeof measure)} value={measure}>{Object.entries(measures).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}{view === "benchmark" && <><label>Occupation<select onChange={(event) => { setOccupation(event.target.value); setSex("Both Sexes"); }} value={occupation}>{benchmarkOccupations.map((item) => <option key={item}>{item}</option>)}</select></label><label>Sex<select onChange={(event) => setSex(event.target.value)} value={sex}>{sexes.map((item) => <option key={item}>{item}</option>)}</select></label></>}</div><p className="grain-note">PUBLISHED SOURCE-GRAIN VALUES · Select, filter, and compare supplied records. Do not sum or average categories.</p><div className="chart-frame wage-chart" aria-label="Wage category chart"><ResponsiveContainer height="100%" width="100%"><BarChart data={chartData} layout="vertical" margin={{ left: 14 }}><CartesianGrid stroke="#26323e" horizontal={false} /><XAxis tickFormatter={(value) => money.format(value)} type="number" /><YAxis dataKey="label" tick={{ fontSize: 11 }} type="category" width={150} /><Tooltip content={<ChartTooltip kind="wage" />} /><Bar dataKey="value" fill="#55c3c6" name={view === "benchmark" ? "Wage Rate" : measures[measure]} /></BarChart></ResponsiveContainer></div><DataView columns={[{ key: labelField, label: view === "regional" ? "Region" : "Industry" }, ...(view === "benchmark" ? [{ key: "benchmark_occupation_name", label: "Occupation" }, { key: "sex", label: "Sex" }] : []), { key: field, label: view === "benchmark" ? "Wage Rate" : measures[measure], format: (value: string | number) => money.format(Number(value)) }]} rows={rows as Record<string, string | number>[]} /><MetricContext definition={definition} /></section>;
}

export function InsightPanel({ people, wage }: { people: PeopleInsightData; wage: WageInsightData }) {
  const [domain, setDomain] = useState<Domain>("people");
  return <main className="journey-panel insight-panel" id="main-content" tabIndex={-1}><p className="panel-stage-number">STAGE 05</p><h1 className="panel-title">INSIGHT</h1><p className="journey-lede">Explore the governed marts.</p><p className="journey-intro">Select existing governed views, inspect exact values, and compare only at their supplied analytical grain.</p><div className="domain-tabs insight-domain-tabs" role="tablist" aria-label="Insight domain"><button aria-selected={domain === "people"} onClick={() => setDomain("people")} role="tab" type="button">People</button><button aria-selected={domain === "wage"} onClick={() => setDomain("wage")} role="tab" type="button">Wage</button></div>{domain === "people" ? <PeopleWorkspace data={people} /> : <WageWorkspace data={wage} />}<div className="insight-links"><Link href="/model">Trace metric model →</Link><Link href="/govern">Inspect governance →</Link></div><footer className="journey-handoff"><p>Governed analytical views make the patterns visible. The final layer determines which signals deserve leadership attention.</p><Link className="journey-link" href="/present">Explore presentation <span aria-hidden="true">→</span></Link></footer></main>;
}