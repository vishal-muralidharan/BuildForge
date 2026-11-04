CREATE TABLE accounts (
  id SERIAL PRIMARY KEY,
  owner_id TEXT NOT NULL,
  balance_cents INTEGER NOT NULL,
  created_at BIGINT NOT NULL
);

ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY accounts_owner_policy ON accounts FOR ALL USING (owner_id = current_user);
