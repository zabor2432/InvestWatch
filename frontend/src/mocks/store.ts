import { seedRecords } from "./generator";

/** Pamięć „bazy” po stronie mocków; wspólna dla MSW i symulatora WS. */
export const store = {
  records: seedRecords(),
  counter: 10000,
};
