# 借鉴能力测评（borrow bench）

一张参考图 → 一页 PPT。参考图与页面内容题材无关，只检验模型能否读懂并转化它的艺术设计。
每个用例跑两组：`ref`（附参考图）与 `control`（同内容、不看参考、不搜参考），由 Claude 盲评。

- 15 个用例见 `cases.json`：5 张模板库页面（香道、旅行、服装、茶品牌画册），10 张公共领域/CC 作品
  （构成主义海报、浮世绘、蒙德里安、哈默修伊、海克尔、维米尔、米纳德、安藤忠雄、霍尔怀因）。
- `learnable`（值得转化的设计关系）和 `traps`（常见误用）只给评审，不发给作者。
- 评分维度：structure / scale / color / typography / devices / content_fit / readability（1–5），
  literal_copy、AI 味清单，以及两两比较 more_transfer（谁更像学到了参考）与 better_page（谁更好）。

```bash
python3 tools/borrow-bench/bench.py prepare            # 拉取参考图到 refs/（不入库）
python3 tools/borrow-bench/bench.py submit r1 --fast   # 提交 30 个单页任务到本地网站
python3 tools/borrow-bench/bench.py wait r1            # 轮询并下载
python3 tools/borrow-bench/bench.py render r1          # Docker 渲染器出图
python3 tools/borrow-bench/bench.py judge r1           # Claude 盲评（A/B 顺序随机）
python3 tools/borrow-bench/bench.py report r1          # runs/r1/report.html 并排对照
```

`--cases b06,b13` 只跑部分用例。指标看三点：ref 组借鉴维度相对 control 的提升、more_transfer 的 ref 胜率，
以及 better_page——借到了但页面变差（照搬、可读性下降）同样是失败。
