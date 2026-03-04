export default function Header() {
  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Legacy
          <span className="text-emerald-400">Lens</span>
        </h1>
        <p className="mt-2 text-sm text-slate-400 sm:text-base">
          RAG-powered legacy code intelligence &mdash; ask questions about COBOL
          and Fortran codebases in natural language
        </p>
      </div>
    </header>
  );
}
