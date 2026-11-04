export function initService() {
  const secret = process.env.API_SECRET;
  const dbUrl = process.env.DATABASE_URL;
  return { secret, dbUrl };
}
