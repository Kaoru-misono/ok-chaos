# 卡牌采集数据

采集任务会把样本写入 `inbox/YYYY-MM-DD/<sample-id>/`：

- `frame.png`：同一轮 OCR 使用的游戏画面，右下角潜在 UID 区域已遮挡。
- `manifest.json`：场景、待审核标签、图片哈希及 OCR 文字坐标。

`inbox`、`approved`、`rejected` 和 `validation` 中的实际图片默认不提交 Git。审核工具尚未确认的样本必须
保持 `review_status: pending`，不得进入正式卡牌数据库或训练集。
