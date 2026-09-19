declare namespace Cloudflare {
  interface Env {
    DB: D1Database;
    FILES: R2Bucket;
    WORKER_TOKEN?: string;
    ADMIN_EMAIL?: string;
    ADMIN_USER_ID?: string;
    REVIEW_TOKEN?: string;
  }
}
