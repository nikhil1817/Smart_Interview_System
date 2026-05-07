export default function EvaluationCard({ evalData }) {
  if (!evalData) return <div>No evaluation yet</div>;

  return (
    <div className="space-y-2 text-sm">
      <div>Score: {evalData.score || 'N/A'}</div>
      <div>Semantic: {evalData.semantic ? evalData.semantic.toFixed(2) : 'N/A'}</div>
      <div>Clarity: {evalData.clarity ? evalData.clarity.toFixed(2) : 'N/A'}</div>
      <div>Vagueness: {evalData.vagueness ? evalData.vagueness.toFixed(2) : 'N/A'}</div>
      <div>STAR: {evalData.star ? evalData.star.toFixed(2) : 'N/A'}</div>
    </div>
  );
}