// Identity must come from Sites' authenticated server headers, never request JSON.
export function adminAllowed(user: {userId:string;email:string}|null, config: {ADMIN_USER_ID?:string;ADMIN_EMAIL?:string}) {
  if(!user) return false;
  if(config.ADMIN_USER_ID?.trim()) return user.userId===config.ADMIN_USER_ID.trim();
  return !!config.ADMIN_EMAIL?.trim() && user.email.toLowerCase()===config.ADMIN_EMAIL.trim().toLowerCase();
}
