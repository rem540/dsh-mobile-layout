## ⚠️ 改这个插件，只改这一个仓库

手机端布局修复插件的**唯一真源**是本仓库的 `src/dsh-mobile-fix.css`。
改完跑 `tools/build.py --profile web`（装到哪个目录它会完整打印出来），重启 `dsh web` 生效。

外面还有几份 CSS 副本，**都别改**：

| # | 路径 | 谁在读 | 该干嘛 |
|---|------|--------|--------|
| 1 | 本仓库 `src/dsh-mobile-fix.css` | `tools/build.py` | ★ 真源，改这里 |
| 2 | `C:\Users\X\.dsh\profiles\web\node_modules\dsh-mobile-layout\` | DSH 的 `web` profile（真在跑） | `--profile web` 装出来的产物 |
| 3 | `dsh-toolkit\plugin\` | 没人读 | 整包复制品（旧的第二仓库），由另一份任务书清掉 |
| 4 | `dsh-toolkit\docs\dsh-mobile-fix.css` | 没人读 | 复制品，同上 |
| 5 | `G:\文档\deepseek-harness\default-workspace\dsh-mobile-fix.css` | 旧的 `build_mobile_plugin.py` | 历史遗留，别再改它 |

两条构建链只有一条算数：本仓库 `tools/build.py`（`src/` → `lib/`，`--profile web` 装进 DSH）。
`dsh-toolkit` 里那个读 G 盘文件的 `build_mobile_plugin.py` 是旧链，已废弃，别再走它。

> 改 `dsh-toolkit` 里的任何一份 CSS，手机上都不会变。
> 真正生效的只有本仓库 `src/dsh-mobile-fix.css` → `tools/build.py --profile web` 这条路。

改完忘了重装？跑 `tools/build.py --check`：把已安装的 `lib/client.js` 里嵌的 CSS 和真源比对，
一致退出码 0，不一致打印两边长度和哈希并退出码 1。

---

# dsh-mobile-layout

DSH（DeepSeek Harness）Web 端的**窄屏布局修复插件**。手机上打开 DSH 时，设置面板和主界面在 700px 以下会挤成一团；这个插件只做一件事：在窄屏下把它们的排版改对。

桌面端（> 700px）**完全不受影响** —— 所有规则都包在 `@media (max-width: 700px)` 里。

## 它修什么

改前是 390px 实测出来的，不是猜的：

```
.wCInkW_panel   [342x796]   disp=flex  dir=row
  nav.wCInkW_nav[188x796]   disp=flex  dir=column   ← 侧栏固定 188px
  .wCInkW_content[154x796]                          ← 只剩 154px
    .wCInkW_options[154x742]                        内边距后内容仅 106px
      .Hefa_q_row [106x77]  disp=flex  dir=row  wrap=nowrap
        .Hefa_q_rowText[48x44]  flex=1/1/0%
          .Hefa_q_title[0x44]  ← 标题宽度被算成 0，"语言"竖成一列
```

| 病 | 表现 | 修法 |
| --- | --- | --- |
| 面板左右分栏 | 手机上只剩 154px 放设置项，「语言」「外观」四个字竖成一列 | 面板改成上下两段、占满整屏（`100dvh`，照顾手机地址栏收起） |
| 侧栏竖排占 188px | 手机上白占一半宽度 | 侧栏折成**顶部横向标签条**，可横滑，`navTitle`（那个"设置"标题）在横排里省掉 |
| 设置行不换行 | 标题被压成 0 宽 | 每行的第一个孩子占满整行，控件换行到下面 |
| 外观三个主题方块挤一行 | 换行成 88px 一格 |
| 点击目标太小 | 字号加减箭头 17×12、开关 36×20，手指按不准 | 箭头热区撑到 32×48，开关 46×28 |
| **右栏被压成 0 宽但仍在布局** | `_rightbarCol` 宽 0、`scrollWidth` 却是 390，于是 `frame` 的 `scrollWidth` = 390+390 = **780**。外层 `overflow-x:hidden` 把它裁掉了，**肉眼看完全正常**，只有量 `scrollWidth` 才现形 | 给 `_rightbarCol` 自己加 `overflow:hidden`，让它成为裁剪容器，不再往父级传导 |
| 设置顶部标签条横滑 | 四个标签 104+76+104+117 = 401px + 间距 = 413，可用只有 366 → 「Agent 预设」被推到屏幕外。滚动条是藏起来的，用户根本不知道还能往右滑 | 宁可换行：四个标签铺两行全都看得见 |

修完（390×844 实测）：出屏元素 **0**、小于 24px 的点击目标 **0**、横向溢出 **false**。

## 安装

插件目录就是你 DSH profile 下的 `node_modules/<包名>`。以 `web` profile 为例：

```bash
python tools/build.py --install ~/.dsh/profiles/web
```

Windows：

```powershell
python tools\build.py --install C:\Users\<你>\.dsh\profiles\web
```

然后**重启 `dsh web`**（插件是启动时扫描的）。装好后浏览器控制台里应该有：

```js
window.__DSH_MOBILE_LAYOUT__   // { rules: 8, bytes: 8544 }
```

`rules` 是真正进入样式表的规则条数。如果它是 `0` 或 `undefined`，说明 CSS 没解析成功（漏个花括号就够了 —— 标签在、长度对、规则 0 条），这时候别去调选择器，先看 CSS 本身。

## 改样式

**唯一真源是 `src/dsh-mobile-fix.css`**，`lib/` 和 `cordis.patch.yml` 都是 `tools/build.py` 生成的，别直接改。

```bash
python tools/build.py                # 只重新生成 lib/
```

## 为什么是插件，不是改 app.asar

改 asar 要重建上万个文件的索引，而且 **DSH 一升级就没了**。DSH 自带客户端插件机制：宿主按包的 `dsh.client` 声明把客户端入口挂在 `/plugins/<包名>/client.js`，入口经 `window.__ModuleLoader__.load` 注册（和 DSH 自带的 `ui-*` 包同一条路径）。

这个插件的形状是照 `dsh-dream-skin` 抄的，两点值得记：

- **`dsh.client.inject` 留空**。别的皮肤插件会声明好几个种子包，因为它们要改主题和设置页。这个插件只往 `<head>` 塞一个 `<style>`，不 `require` 任何东西 —— 声明得越多，将来 DSH 改版时被牵动的面越大。
- **整段包在 `try` 里**。加载器条目的工厂函数一旦抛异常，会聚合进 "entries did not activate"，把整个 web shell 拖下水。一个改样式的插件绝不该有这个本事。

## 选择器为什么长这样

class 名是 CSS Modules 生成的"**哈希_语义后缀**"，哈希随构建变、后缀不变，所以只能匹配后缀。踩过的三个坑：

1. **子串选择器会误伤**。`[class*="_nav"]` 同时命中 `_navList` / `_navCell` / `_navTitle` —— 第一版把它们强行改成横排，整个导航塌了，面板一片空白。现在侧栏只用元素标签锚定：`nav[class*="_nav"]`，全页面只有它一个是 `<nav>`。
2. **`[role=dialog]` 本身就是 `_panel`**，不是它的子元素。写成 `[role='dialog'] > [class*='_panel']` 全场零匹配。
3. **CSS 没有父选择器**。要"选中行的容器"时用 `:has(> …)`；直接写 `[class*="_row"]` 会连 `_rowText` 一起匹配，分不开。

另外：`_row` 的第一个孩子是个**没有该类的裸 `<div>`**，只认类名会漏掉它，所以规则写成"每一行的第一个孩子"。

## 许可

MIT，见 [LICENSE](LICENSE)。
