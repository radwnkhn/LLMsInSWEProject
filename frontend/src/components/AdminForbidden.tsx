export function AdminForbidden() {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-bold">403: Admins only</h1>
      <p className="text-zinc-600">Your account doesn&apos;t have admin access.</p>
    </div>
  );
}
