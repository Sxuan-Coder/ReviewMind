type RiskSummaryProps = {
  riskLevel: string;
  findingCount: number;
};

export function RiskSummary({ riskLevel, findingCount }: RiskSummaryProps) {
  return (
    <div className="risk-grid">
      <div className="metric-card">
        <span>当前风险等级</span>
        <strong>{riskLevel}</strong>
      </div>
      <div className="metric-card">
        <span>风险发现</span>
        <strong>{findingCount}</strong>
      </div>
      <div className="metric-card">
        <span>报告状态</span>
        <strong>占位可用</strong>
      </div>
    </div>
  );
}