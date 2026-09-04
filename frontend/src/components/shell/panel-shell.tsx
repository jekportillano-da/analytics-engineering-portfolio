import { getLifecycleStage, type LifecycleStageId } from "@/lib/navigation/lifecycle";

export function PanelShell({ stageId }: { stageId: LifecycleStageId }) {
  const stage = getLifecycleStage(stageId);

  return (
    <main className="panel-shell" id="main-content" tabIndex={-1}>
      <p className="panel-stage-number">STAGE {stage.number}</p>
      <h1 className="panel-title">{stage.title}</h1>
      <p className="panel-question">{stage.question}</p>
      <section aria-label={`${stage.title} content status`} className="deferred-panel">
        Panel content intentionally deferred.
      </section>
    </main>
  );
}