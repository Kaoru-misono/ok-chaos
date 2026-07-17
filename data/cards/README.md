# 角色牌数据库

这里仅收录角色专属卡牌及其普通闪、专属灵光一闪、神圣闪光和角色专属强化变体。中立牌、怪物牌不进入数据库；
识别时无法可靠匹配到角色牌的数据必须返回 `unknown` 或 `unsupported`。

每个角色使用一个 `characters/*.json` 文件，顶层格式为：

```json
{
  "schema_version": 1,
  "owner": {
    "owner_id": "character_id",
    "name": {"zh_cn": "简体角色名", "zh_tw": "繁體角色名"}
  },
  "cards": [],
  "variants": []
}
```

ID 必须使用稳定的小写 ASCII 字符，不要使用会随本地化变化的中文名称。卡牌事实必须经过人工核对；
采集器输出的 OCR 文本只能作为待审核证据，不能直接复制为正式数据。

当前试点角色为 `haide_mali`（简体“海德玛丽”、繁体“海德瑪麗”）。

完整字段示例见 `characters/character.template.json.example`。运行下列命令校验全部数据：

```powershell
.\scripts\cards.ps1 validate-catalog
```
