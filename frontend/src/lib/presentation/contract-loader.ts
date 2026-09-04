import "server-only";

import { readFile } from "node:fs/promises";
import path from "node:path";

const CONTRACT_ID = "analytics-portfolio-presentation-v1";
const CONTRACT_VERSION = 1;
const ARTIFACT_TYPES = ["insights", "platform", "people", "wage", "quality", "lineage"] as const;

type ArtifactType = (typeof ARTIFACT_TYPES)[number];

export type PresentationArtifactMetadata = {
  artifactId: `presentation.${string}.v1`;
  artifactType: ArtifactType;
  contractId: typeof CONTRACT_ID;
  contractVersion: typeof CONTRACT_VERSION;
};

export type PresentationContract = Readonly<Record<ArtifactType, PresentationArtifactMetadata>>;

export type GovernanceCheck = {
  check_type: string;
  detail: string;
  domain: string;
  evaluated_at: string;
  expected_value: string;
  governance_check_id: string;
  latest_operational_at: string | null;
  observed_value: string;
  status: string;
};

export type GovernedHealthSnapshot = {
  freshness_contracts: Record<string, { error_after_hours: number; operational_timestamp: string; reference_period: string; warn_after_hours: number }>;
  governance_checks: GovernanceCheck[];
  health_semantics: string;
  people_quality: { issue_count: number; by_type: { issue_count: number; severity: string }[] };
  people_reconciliation: { summary: { maximum_difference: number; period_count: number; reconciled_period_count: number } };
  wage_reconciliation: { summary: { maximum_difference: number; matrix_count: number; reconciled_matrix_count: number; mart_observation_count: number } };
};

export type MetricDefinition = { metric_id: string; definition: string; aggregation_behavior: string; limitations: string; time_grain?: string };
export type PeopleMonthlyRecord = { period_start: string; period_end: string; ending_headcount: number; hires: number; separations: number; attrition_rate: number };
export type PeopleInsightData = { definitions: MetricDefinition[]; monthly: PeopleMonthlyRecord[] };
export type WageCategoryRecord = { reference_year: number; industry_name?: string; region_name?: string; benchmark_occupation_name?: string; sex?: string; average_monthly_basic_pay?: number; average_monthly_allowance?: number; average_monthly_wage_rate: number };
export type WageInsightData = { definitions: MetricDefinition[]; industry: WageCategoryRecord[]; regional: WageCategoryRecord[]; benchmark_occupations: WageCategoryRecord[] };
export type ExecutiveEvidence = { artifact_id: string; collection: string; record_key: string | null; record_id: string | null; field: string; observed_value: string | number; metric_id: string | null; governed_source: string; period: string | number | null; dimensions: Record<string, string> };
export type ExecutiveInsight = { insight_id: string; domain: "people" | "wage" | "platform"; question_id: string; executive_question: string; headline: string; narrative: string; evidence_state: string; evidence: ExecutiveEvidence[]; metric_ids: string[]; limitations: string[]; next_question_ids: string[] };

function assertEnvelope(value: unknown, artifactType: ArtifactType, filePath: string): PresentationArtifactMetadata {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`Presentation contract error in ${filePath}: expected an object envelope.`);
  }

  const artifact = value as Record<string, unknown>;
  const expectedId = `presentation.${artifactType}.v1`;
  if (
    artifact.contract_id !== CONTRACT_ID ||
    artifact.contract_version !== CONTRACT_VERSION ||
    artifact.artifact_id !== expectedId ||
    artifact.artifact_type !== artifactType ||
    typeof artifact.data !== "object" ||
    artifact.data === null ||
    Array.isArray(artifact.data)
  ) {
    throw new Error(`Presentation contract error in ${filePath}: incompatible V1 ${artifactType} artifact.`);
  }

  return {
    artifactId: expectedId as PresentationArtifactMetadata["artifactId"],
    artifactType,
    contractId: CONTRACT_ID,
    contractVersion: CONTRACT_VERSION,
  };
}

export async function loadPresentationContract(): Promise<PresentationContract> {
  const dataDirectory = path.resolve(process.cwd(), "..", "presentation", "data");
  const entries = await Promise.all(
    ARTIFACT_TYPES.map(async (artifactType) => {
      const filePath = path.join(dataDirectory, `${artifactType}.json`);
      let source: string;
      try {
        source = await readFile(filePath, "utf8");
      } catch (error) {
        throw new Error(`Presentation contract error: unable to read ${filePath}.`, { cause: error });
      }
      try {
        return [artifactType, assertEnvelope(JSON.parse(source), artifactType, filePath)] as const;
      } catch (error) {
        if (error instanceof SyntaxError) {
          throw new Error(`Presentation contract error in ${filePath}: invalid JSON.`, { cause: error });
        }
        throw error;
      }
    }),
  );

  return Object.fromEntries(entries) as PresentationContract;
}

export async function loadGovernedHealthSnapshot(): Promise<GovernedHealthSnapshot> {
  const filePath = path.resolve(process.cwd(), "..", "presentation", "data", "quality.json");
  const artifact = JSON.parse(await readFile(filePath, "utf8")) as Record<string, unknown>;
  assertEnvelope(artifact, "quality", filePath);
  const data = artifact.data as Record<string, unknown>;
  const required = ["freshness_contracts", "governance_checks", "health_semantics", "people_quality", "people_reconciliation", "wage_reconciliation"];
  if (!required.every((key) => key in data) || !Array.isArray(data.governance_checks)) {
    throw new Error(`Presentation contract error in ${filePath}: invalid governed health payload.`);
  }
  return data as unknown as GovernedHealthSnapshot;
}

async function loadArtifactData(artifactType: "people" | "wage") {
  const filePath = path.resolve(process.cwd(), "..", "presentation", "data", `${artifactType}.json`);
  const artifact = JSON.parse(await readFile(filePath, "utf8")) as Record<string, unknown>;
  assertEnvelope(artifact, artifactType, filePath);
  return { data: artifact.data as Record<string, unknown>, filePath };
}

export async function loadInsightData(): Promise<{ people: PeopleInsightData; wage: WageInsightData }> {
  const [{ data: people, filePath: peoplePath }, { data: wage, filePath: wagePath }] = await Promise.all([loadArtifactData("people"), loadArtifactData("wage")]);
  const validDefinitions = (value: unknown) => Array.isArray(value) && value.every((item) => typeof item === "object" && item !== null && typeof (item as Record<string, unknown>).metric_id === "string");
  const validPeopleRows = Array.isArray(people.monthly) && people.monthly.every((item) => typeof item === "object" && item !== null && ["period_start", "period_end", "ending_headcount", "hires", "separations", "attrition_rate"].every((key) => key in item));
  const validWageRows = (value: unknown) => Array.isArray(value) && value.every((item) => typeof item === "object" && item !== null && typeof (item as Record<string, unknown>).average_monthly_wage_rate === "number");
  if (!validDefinitions(people.definitions) || !validPeopleRows || !validDefinitions(wage.definitions) || !validWageRows(wage.industry) || !validWageRows(wage.regional) || !validWageRows(wage.benchmark_occupations)) {
    throw new Error(`Presentation contract error: incompatible INSIGHT data in ${peoplePath} or ${wagePath}.`);
  }
  return { people: people as unknown as PeopleInsightData, wage: wage as unknown as WageInsightData };
}

function resolveCollection(data: Record<string, unknown>, collection: string) {
  return collection.split(".").reduce<unknown>((current, key) => typeof current === "object" && current !== null ? (current as Record<string, unknown>)[key] : undefined, data);
}

export async function loadExecutiveBriefing(): Promise<ExecutiveInsight[]> {
  const directory = path.resolve(process.cwd(), "..", "presentation", "data");
  const rawArtifacts = await Promise.all(ARTIFACT_TYPES.map(async (type) => {
    const filePath = path.join(directory, `${type}.json`);
    const artifact = JSON.parse(await readFile(filePath, "utf8")) as Record<string, unknown>;
    assertEnvelope(artifact, type, filePath);
    return [type, artifact.data as Record<string, unknown>] as const;
  }));
  const artifacts = Object.fromEntries(rawArtifacts) as Record<ArtifactType, Record<string, unknown>>;
  const insightData = artifacts.insights;
  if (insightData.insight_contract_id !== "analytics-portfolio-executive-insights-v1" || insightData.insight_contract_version !== 1 || !Array.isArray(insightData.insights)) throw new Error("Presentation contract error: incompatible Executive Insight Contract.");
  const insights = insightData.insights as ExecutiveInsight[];
  const questionIds = new Set(insights.map((insight) => insight.question_id));
  for (const insight of insights) {
    if (!["people", "wage", "platform"].includes(insight.domain) || !insight.insight_id || !insight.question_id || !insight.headline || !insight.narrative || !Array.isArray(insight.evidence) || !Array.isArray(insight.limitations) || !Array.isArray(insight.next_question_ids) || !insight.next_question_ids.every((id) => questionIds.has(id))) throw new Error(`Presentation contract error: invalid executive insight ${insight.insight_id}.`);
    for (const evidence of insight.evidence) {
      const artifactType = evidence.artifact_id.replace("presentation.", "").replace(".v1", "") as ArtifactType;
      const collection = artifacts[artifactType] && resolveCollection(artifacts[artifactType], evidence.collection);
      const record = Array.isArray(collection) && evidence.record_key ? collection.find((item) => typeof item === "object" && item !== null && (item as Record<string, unknown>)[evidence.record_key!] === evidence.record_id) : collection;
      if (typeof record !== "object" || record === null || (record as Record<string, unknown>)[evidence.field] !== evidence.observed_value) throw new Error(`Presentation contract error: unresolved evidence for ${insight.insight_id}.`);
    }
  }
  return insights;
}