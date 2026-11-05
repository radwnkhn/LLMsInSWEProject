import { useId } from "react";

import type { NotMeasuredCheck } from "@/lib/types";

export function NotMeasured({ items }: { items: NotMeasuredCheck[] }) {
  const titleId = useId();
  if (!items.length) return null;
  return (
    <section aria-labelledby={titleId} className="space-y-1">
      <h2 id={titleId} className="text-lg font-semibold">Not measured</h2>
      <p className="text-sm text-zinc-600">We don&apos;t guess. These checks couldn&apos;t be measured from this video:</p>
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {items.map((i) => <li key={i.check}>{`${i.name}: ${i.reason}`}</li>)}
      </ul>
    </section>
  );
}
