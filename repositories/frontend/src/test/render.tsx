import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation, useRoutes, type Location } from "react-router";

import { Providers } from "@/app/Providers";
import { routes } from "@/app/routes";

/** The app's routes under a declarative router. (The data router used in the browser builds
 * a Request per navigation with jsdom's AbortSignal, which Node's fetch rejects.) */
function AppRoutes({ onLocation }: { onLocation: (location: Location) => void }) {
  onLocation(useLocation());
  return useRoutes(routes);
}

/** Render the whole app at ``path``, with a fresh query cache and no retries. */
export function renderApp(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  const user = userEvent.setup();
  const current: { location: Location | null } = { location: null };
  const view = render(
    <Providers client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes onLocation={(location) => (current.location = location)} />
      </MemoryRouter>
    </Providers>,
  );
  return { ...view, client, user, location: () => current.location! };
}
