export const statuses=['queued','running','complete','failed'] as const;
export function adminQuery(url:URL) {
  const status=url.searchParams.get('status')||'';
  if(status && !statuses.includes(status as typeof statuses[number])) throw Error('Invalid status');
  const search=(url.searchParams.get('q')||'').trim();
  if(search.length>200) throw Error('Search is too long');
  const raw=url.searchParams.get('page')||'1';
  if(!/^[1-9]\d{0,5}$/.test(raw)) throw Error('Invalid page');
  const page=Number(raw),limit=25;
  const clauses:string[]=[],args:(string|number)[]=[];
  if(status){clauses.push('status=?');args.push(status);}
  // Literal substring search avoids D1's restricted LIKE pattern complexity.
  if(search){clauses.push('(instr(lower(title),lower(?))>0 OR instr(lower(brief),lower(?))>0 OR instr(user_id,?)>0 OR instr(id,?)>0)');args.push(search,search,search,search);}
  return {where:clauses.length?'WHERE '+clauses.join(' AND '):'',args,page,limit,offset:(page-1)*limit};
}
