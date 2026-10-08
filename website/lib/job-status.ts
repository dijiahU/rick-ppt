// Preserve storage compatibility while distinguishing a reviewed upload retry.
export function publicJobStatus(status:unknown,summary:unknown):string {
  return status==='failed'&&summary==='delivery_pending'?'delivery_pending':String(status);
}
