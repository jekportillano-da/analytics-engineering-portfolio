export const lifecycleStages = [
  { id: "source", number: "01", title: "SOURCE", question: "Where does the raw data originate, and is the source reliable enough to use?", tooltip: "Raw origin, authority, grain, scope and limitations." },
  { id: "ingest", number: "02", title: "INGEST", question: "How is the data acquired, preserved, and landed reliably?", tooltip: "Acquisition, preservation, provenance and engineering decisions." },
  { id: "model", number: "03", title: "MODEL", question: "How does raw data become reusable analytical structure?", tooltip: "Transform raw source structures into reusable analytical models." },
  { id: "govern", number: "04", title: "GOVERN", question: "How do we determine whether the resulting data product can be trusted?", tooltip: "Validate quality, freshness, reconciliation and trust." },
  { id: "insight", number: "05", title: "INSIGHT", question: "What does the governed analytical data look like?", tooltip: "Explore governed marts through analytical views." },
  { id: "present", number: "06", title: "PRESENT", question: "What matters to leadership?", tooltip: "Distill validated evidence into executive reporting." },
] as const;

export type LifecycleStageId = (typeof lifecycleStages)[number]["id"];

export function getLifecycleStage(stageId: LifecycleStageId) {
  return lifecycleStages.find((stage) => stage.id === stageId)!;
}