'use client';
import {useLanguage} from './language';
import {queueWords} from '@/lib/queue-i18n';
import {queueReason,type QueueHealth} from '@/lib/queue-state';

export default function QueueStatus({queue,position,createdAt}:{queue:QueueHealth;position?:number|null;createdAt?:number}) {
  const {locale}=useLanguage(),w=queueWords[locale];
  const waited=createdAt??queue.oldestQueuedAt;
  return <section className={`queue-status ${queue.online?'':'queue-offline'}`} aria-label={w.queue}>
    <h2>{w.queue}</h2><p>{w[queueReason(queue)]}</p>
    <dl><div><dt>{w.running}</dt><dd>{queue.running} / {queue.capacity}</dd></div>
      {position!=null&&<div><dt>{w.position}</dt><dd>#{position}</dd></div>}
      {waited!=null&&<div><dt>{createdAt!=null?w.waited:w.oldest}</dt><dd>{Math.max(0,Math.floor((queue.checkedAt-waited)/60000))} {w.minutes}</dd></div>}
      <div><dt>{w.lastSeen}</dt><dd>{queue.lastHeartbeat===null?w.neverSeen:new Date(queue.lastHeartbeat).toLocaleString(locale)}</dd></div>
    </dl>
  </section>;
}
