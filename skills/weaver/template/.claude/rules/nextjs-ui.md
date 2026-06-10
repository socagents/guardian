---
paths:
  - "services/ui/**"
---

# Next.js UI Conventions

## Language and Tooling

- TypeScript strict mode. No `any`.
- Framework: Next.js 14+ with App Router.
- Styling: Tailwind CSS.
- Package manager: pnpm.
- Lint: `pnpm lint` (ESLint).
- Test: `pnpm test` (Vitest for unit, Playwright for E2E).

## Code Style

- React Server Components by default. Use `"use client"` only when needed.
- camelCase for variables/functions. PascalCase for components and types.
- Colocate components, hooks, and utils near their usage.
- Extract reusable components into `components/`. Page-specific ones stay in the route dir.

## Testing

- Unit tests: Vitest with React Testing Library.
- E2E tests: Playwright (test files in `e2e/` or `tests/`).
- Mock API calls in unit tests. Use real API in E2E with test fixtures.
- Target 80%+ coverage on new code.

## Project Structure

- App Router: routes in `app/` directory.
- Shared components in `components/`.
- Server actions in `actions/` or colocated with routes.
- API route handlers in `app/api/`.

## Accessibility

- All interactive elements must be keyboard accessible.
- Use semantic HTML elements.
- Include `aria-label` for icon-only buttons.
- Test with Playwright accessibility assertions where applicable.
