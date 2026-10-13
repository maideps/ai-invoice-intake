import { Link } from "react-router";

import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center gap-3 py-20 text-center">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="text-sm text-muted">That address doesn't match anything here.</p>
      <Button asChild>
        <Link to="/">Go to the review queue</Link>
      </Button>
    </div>
  );
}
