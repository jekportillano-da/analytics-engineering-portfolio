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