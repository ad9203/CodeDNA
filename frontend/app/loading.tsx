export default function Loading() {
  return (
    <div className="min-h-screen bg-slate-950 p-8">
      <div className="max-w-7xl mx-auto space-y-6 animate-pulse">
        <div className="h-10 bg-slate-900 rounded w-1/4"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="h-24 bg-slate-900 rounded"></div>
          <div className="h-24 bg-slate-900 rounded"></div>
          <div className="h-24 bg-slate-900 rounded"></div>
          <div className="h-24 bg-slate-900 rounded"></div>
        </div>
        <div className="h-96 bg-slate-900 rounded"></div>
      </div>
    </div>
  );
}
