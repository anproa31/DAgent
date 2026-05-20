export function parseDatasourceError(
  error: unknown,
  fallback: string
): { message: string; details: string } {
  const message =
    (error as { response?: { data?: { detail?: string } }; message?: string })
      ?.response?.data?.detail ||
    (error instanceof Error ? error.message : fallback)
  const details = error instanceof Error ? error.stack ?? '' : ''
  return { message, details }
}
