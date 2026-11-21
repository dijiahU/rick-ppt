# Worked examples: from content to page

Each example shows the plain page a model produces by default, the page design sheet
(art-direction.md) worked out, and why the result reads faster. Learn the reasoning,
not the layouts: the same content in another deck may need a different answer.

## 1. Split one crowded page into a sequence (lesson)

Content: in 1793 the Italian biologist Lazzaro Spallanzani showed by experiment that
bats find their way by hearing, not sight.

Plain version: one page with a portrait, a bat photo, a paragraph and a title. The
audience must read four things at once and decide the order themselves.

- Takeaway: bats navigate by hearing.
- Relationship: who (the scientist), what (the bat), how (the finding).
- Steps: three, one at a time. With pages to spare: scientist page, bat page, a page
  where the word "听觉" is the hero. With one page: three clicks on the same page.
- Hero: step 1 the portrait, step 2 the bat, step 3 "听觉" set very large.
- Reading order: ① who ② what was tested ③ the answer.
- Cut: the paragraph; the speaker tells the story.
- Visual idea: the answer arrives last and largest, like a reveal.
- Rejected: everything on one page with a caption under each picture: no order, the
  answer is the smallest text.

## 2. One number against the trend (weekly report)

Content: support tickets fell 18% (612 → 502), mostly login issues; payment-failure
tickets rose by 23, cause under investigation, suspected new payment callback.

Plain version: title "客服工单情况" over three equal cards (总量 / 支付失败 / 排查方向).
Three equal cards say three equal things; the one that needs action is lost.

- Takeaway: "支付失败类工单增加 23 单，原因仍在排查".
- Relationship: how much, and one exception against a falling total.
- Steps: ① the exception ② the context (total fell) ③ the next action.
- Hero: "+23 单", about 40% of the page height, in the one accent colour.
- Reading order: ① +23 ② total 612 → 502 small, as context ③ 排查建议.
- Cut: a second chart of the same totals; adjectives such as "明显".
- Visual idea: +23 is the only figure going up on a page where everything else goes
  down; the total is drawn quietly so the exception stands out.
- Rejected: a bar chart of all ticket types: correct but the reader must find the
  exception. The unit "单" must sit on the number's baseline at a smaller size; a unit
  overlapping its digits is a build error, not a style.

## 3. A before/after that shows the change (weekly report)

Content: registration cut from 4 steps to 2 (WeChat one-tap login); conversion
3.1% → 4.6%; daily sign-ups 820 → 1,210.

Plain version: two-column table "上线前 / 上线后" with three rows.

- Takeaway: "注册由 4 步减至 2 步，转化率升至 4.6%".
- Relationship: cause (fewer steps) and effect (higher conversion).
- Steps: ① the cause ② the main effect ③ the second effect.
- Hero: the step blocks (4 grey, 2 in the accent) and "4.6%".
- Reading order: ① 4 → 2 blocks ② 3.1% → 4.6% ③ 820 → 1,210.
- Cut: a bar chart with two bars per metric (adds axes, no information).
- Visual idea: the process itself gets shorter on the page, so the cause is seen,
  not read.
- Rejected: the table: every cell has equal weight and the cause is a row label.

## 4. Where: draw the route, ask the question (lesson)

Content: from Chang'an westward through the Hexi Corridor and Dunhuang, splitting
north and south around the Taklamakan, to Central Asia, West Asia and the
Mediterranean; goods changed hands in stages.

Plain version: a bullet list of places, or a horizontal timeline of place names.

- Takeaway: silk travelled along a branching route, relayed by many merchants.
- Relationship: where (a map).
- Steps: ① the main line from Chang'an ② the branches ③ the relay points.
- Hero: the route line across the full width, east on the right as the class reads it.
- Reading order: ① 长安 ② the branching line ③ the green relay circles and the question.
- Cut: exact distances and modern borders; mark the map "示意，非按比例".
- Visual idea: the question "一匹丝绸，要由一位商人运完全程吗？" sits under the map,
  and the relay circles answer it.
- Rejected: a timeline of places: it implies time, not geography.

## 5. Fixing a reading order the reviewer flagged (lesson)

Content: why Zhang Qian went west: task, result, what he brought back; a Mogao
mural of the mission.

What went wrong: the large mural on the right was seen first; the task on the left,
which is the point, came third. The page answered "what does the mural look like"
before "why did he go".

- Takeaway: he went to win an ally against the Xiongnu; the alliance failed, but the
  report opened contact.
- Reading order wanted: ① the question in the headline ② the task ③ the mural as
  evidence.
- Fix: make the task the larger, left-hand block in the accent colour; reduce the
  mural to the evidence column with its caption; reveal the mural on the second click.
- Rule learned: a striking picture always wins the first look. Give it the hero role
  only when it is the point.

## 6. Part of a whole, not two KPI cards (company profile)

Content: 42 employees, 11 of them registered architects.

Plain version: two cards, "42 名员工" and "11 名注册建筑师", side by side, equal size.

- Takeaway: a small firm with a high share of registered architects.
- Relationship: part of a whole.
- Hero: one bar of 42 marks with 11 filled, and "42" large.
- Reading order: ① 42 ② the filled 11 ③ the label.
- Visual idea: the reader counts the share instead of reading two numbers.
- Rejected: a pie chart: hard to count, and too big for one ratio.

## 7. Ask for a decision at the end (weekly report)

Content: next week, member-points redesign; plan review on Wednesday; needs one
designer and one back-end engineer.

Plain version: "下周计划" with three bullets, or a "感谢观看" closing page.

- Takeaway: "请协调设计、后端各 1 人，下周三评审".
- Relationship: two inputs converging on one date.
- Hero: "下周三", with the two roles leading into it.
- Reading order: ① the request ② the two roles ③ the date.
- Visual idea: two lines (设计 1 人, 后端 1 人) meet at one point labelled 下周三:
  the request and its deadline are one picture.
- Rejected: "感谢观看": the meeting's last minute is the best moment to ask.

## 8. A template graphic must mean what it shows (template base page)

Content: points redesign, Wednesday review, one designer, one back-end engineer,
placed into a template page with four overlapping circles.

What went wrong: overlapping circles say "these four things share common ground".
A date, a project and two roles share nothing; the graphic told a false story.

- Before reusing a template diagram, write what shape, overlap, direction and grey
  mean. Overlap = shared parts; arrows = sequence or cause; a pyramid = hierarchy.
- Fix: choose the template page with two equal picture slots for the two roles and
  put the date in the shared headline area; or build the convergence of example 7.
- Rule learned: when no template page carries the relationship, mark the page `new`
  and build it.
