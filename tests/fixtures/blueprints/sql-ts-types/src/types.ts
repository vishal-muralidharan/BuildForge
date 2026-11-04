export interface AccountSummary {
  id: string;
  ownerId: string;
  balanceCents: number;
}

export type TransactionType = "credit" | "debit";
