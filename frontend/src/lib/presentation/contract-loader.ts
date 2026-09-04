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