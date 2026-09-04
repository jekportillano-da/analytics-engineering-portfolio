import { PresentPanel } from "@/components/journey/present-panel";
import { loadExecutiveBriefing } from "@/lib/presentation/contract-loader";

export default async function PresentPage() {
  return <PresentPanel insights={await loadExecutiveBriefing()} />;
}