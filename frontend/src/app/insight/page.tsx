import { InsightPanel } from "@/components/journey/insight-panel";
import { loadInsightData } from "@/lib/presentation/contract-loader";

export default async function InsightPage() {
  const { people, wage } = await loadInsightData();
  return <InsightPanel people={people} wage={wage} />;
}