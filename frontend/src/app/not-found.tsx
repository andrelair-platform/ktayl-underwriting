import Link from "next/link";

export default function NotFound() {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
      <h1 className="text-lg font-semibold text-slate-800">Not found</h1>
      <p className="mt-1 text-sm text-slate-500">That submission does not exist.</p>
      <Link href="/" className="mt-4 inline-block text-sm font-medium text-indigo-600 hover:underline">
        ← Back to the inbox
      </Link>
    </div>
  );
}
