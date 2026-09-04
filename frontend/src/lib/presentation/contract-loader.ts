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