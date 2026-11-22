# frontend/ (React 18 + TypeScript + Tailwind)

Applies on top of the root `AGENTS.md`. Run `npm run typecheck && npm test && npm run build` here.

- Presentational components take props; data logic lives in hooks (`src/hooks`). Pure logic is in `src/domain` and covered by vitest (node env, `*.test.ts`).
- Only `src/api/mappers.ts` knows the backend body shape (`src/api/dto.ts`); components use the domain model from `src/domain/types.ts`.
- Risk is always shown with a text label, not colour alone. UI strings are Polish. No `console.log` (use `src/lib/log.ts`).
- Raw model scores stay in the data; thresholds are applied on the client (calibration). Blind mode hides model output until the user submits a rating.
- `src/mocks` (MSW) is dev-only: `npm run dev` uses it (`.env.development`), the Docker image is built with `VITE_USE_MOCKS=false` and contains no mock code.
- `npm run build:demo` writes the committed static demo (`demo/dashboard-static`: mocks plus generated analyst ratings); rebuild and commit it with every frontend change, CI checks it.
- Recharts for charts; reuse `components/ui/*` (`Button`, `MultiSelect`) and the `Card` from `KpiCards.tsx` before adding components.
