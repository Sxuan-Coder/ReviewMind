type ProgressTimelineProps = {
  activeStep: string;
};

const steps = [
  'Fetch PR',
  'Diff Filter',
  'AST Context',
  'Agent Review',
  'Risk Judge',
  'Report',
];

export function ProgressTimeline({ activeStep }: ProgressTimelineProps) {
  return (
    <div className="timeline-card">
      <div className="section-label">Agent Workflow</div>
      <div className="timeline-list">
        {steps.map((step) => (
          <div className="timeline-item" key={step}>
            <span className={activeStep === step ? 'timeline-dot active' : 'timeline-dot'} />
            <span>{step}</span>
          </div>
        ))}
      </div>
    </div>
  );
}