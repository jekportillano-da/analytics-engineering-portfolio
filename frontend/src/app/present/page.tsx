import { Suspense } from "react";
import { PresentPanel } from "@/components/journey/present-panel";
import { loadExecutiveBriefing } from "@/lib/presentation/contract-loader";

export default async function PresentPage() {
  const insights = await loadExecutiveBriefing();
  return <Suspense fallback={null}><PresentPanel insights={insights} /></Suspense>;
}