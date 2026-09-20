# Live conversation: follow current work

Opening the real CNN task in the signed-in browser exposed a usability defect:
long conversations initially stayed at their oldest message. A long incoming
reply could also push the reader away from the end because the old check measured
the distance only after appending the reply.

The panel now remembers whether the reader is following the conversation and
scrolls after layout. Initial history opens at the latest message; new replies
remain visible when already following. Scrolling up preserves the reading
position. Sending a message returns to its result. Messages, attachments and
existing task data are unchanged.

A new local browser check reproduced the old reload failure before the fix.
The corrected real-route exercise passed 13 scenarios covering uploads, replies,
acknowledgement, applied status, reload, ordinary chat, reconnect, long history,
reading-position preservation, long incoming replies, sending, recovery and
mobile layout. A separate resize check kept the final message visible when
changing from 1440 to 390 pixels wide. TypeScript and the production build pass.
The actual desktop and mobile captures were inspected; credentials and old data
are excluded from the proof.

Private evidence: `proof/site-chat-scroll-63fxg9ob`. Its retained `before/`
directory includes the failure, original component and screenshot. Local fixtures
are new synthetic jobs and never enter the production queue.

Published as website **v33**, source
`d1f7d2ef7e416cb060f1ca778fcdf69ec1bba4b4`; deployment succeeded at
[PPTX LAB](https://rick-ppt.woodsy-crane-8759.chatgpt.site).
The validated archive has 142 files, SHA-256
`36c17ea9961f8c35f4436ac2f51fb875456ee029b7524f240b0531c865e404ee`.
Its public audience is unchanged. This release changes no schema or worker
protocol and does not certify either teaching case.
