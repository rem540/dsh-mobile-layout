# dsh-mobile-layout · 给 AI 的任务书

工作目录：`F:\Fendou\projects\dsh-mobile-layout`
远端：`git@github.com:rem540/dsh-mobile-layout.git`（SSH），分支 `main`，当前 HEAD `eb80a97`

---

## 〇 你要粘贴给 Trae 的起手式

```
读 F:\Fendou\projects\dsh-mobile-layout\给AI的任务.md，按里面的任务从头做到尾。

做完一条直接做下一条，不要问「要不要继续」，答案永远是继续。
只有两种情况停下来告诉我：(a) 任务描述与实际代码严重对不上；(b) 某条验收怎么都过不去。

不要 git commit、不要 git push，做完我自己验收。
用 E:\anaconda\python.exe，不要新建虚拟环境。
```

---

## 〇之二 这个仓库是什么，以及为什么现在要动它

**它是什么**：DSH Web 端在**窄屏（< 700px，手机）**下的布局修复插件。
桌面端（> 700px）完全不受影响 —— 所有规则都包在 `@media (max-width: 700px)` 里。

它只做一件事：往 `<head>` 塞一个 `<style>`。不 require 任何东西、
不碰 cordis 上下文 —— 少一个依赖就少一种随 DSH 升级而失效的方式。

**为什么现在要动它**：因为它**有两个仓库、四份一模一样的 CSS、两条构建链**，
而且**真正在跑的那条链不在这个仓库里**。

我查实的现状：

```
F:\Fendou\projects\dsh-mobile-layout\      ← 这个仓库（真身，有独立远端）
    .gitignore LICENSE README.md cordis.patch.yml package.json
    lib/client.js lib/index.js src/dsh-mobile-fix.css tools/build.py

F:\Fendou\projects\dsh-toolkit\plugin\     ← 同样的 9 个文件又有一份
                                              （9/9 字节级相同，被 dsh-toolkit 的 git 跟踪着）
```

CSS 有四份，**内容全部相同**（SHA256 `BEC41D25C266…`，8544 B）：

| # | 路径 | 谁在读 |
|---|---|---|
| 1 | `G:\文档\deepseek-harness\default-workspace\dsh-mobile-fix.css` | ★ **真在跑的那条链读它** |
| 2 | `dsh-toolkit\plugin\src\dsh-mobile-fix.css` | 没人读 |
| 3 | `dsh-toolkit\docs\dsh-mobile-fix.css` | 没人读 |
| 4 | **`这个仓库\src\dsh-mobile-fix.css`** | 本仓库的 `tools/build.py` 读它 —— **但那条链从没被用过** |

两条构建链：

| 脚本 | 读 | 写到 | 状态 |
|---|---|---|---|
| `dsh-toolkit\src\dsh_toolkit\build_mobile_plugin.py` | **G 盘那份**（写死） | `C:\Users\X\.dsh\profiles\web\node_modules\dsh-mobile-layout` | ★ **就是它装的，真在跑** |
| **本仓库 `tools/build.py`** | 本仓库 `src/` | 本仓库 `lib/`，`--install` 可装 | 写法更干净，**但从没装过** |

**插件只装在 `web` 这一个 profile 里**（`desktop` / `headless` / `verify5` 都没有）。

**已核对的两个差异**（不影响功能，但要知道）：
- 装到 `profiles\web` 那份的 `package.json` 有 `"private": true`，本仓库的没有；
- 那份 `lib/client.js` 和本仓库的**只差 11 行注释**，**嵌进去的 CSS 字节相同**（6053 字符 = 8544 B 那份转义后）。

**所以现在还没坏，但已经在坏的路上了。** 这一轮要做的事：

1. **把「本仓库是真源」这件事钉死**（写进 README，让下一个人不会再改错地方）
2. **把本仓库的构建脚本补成唯一入口**（加 `--profile` 和 `--check`）
3. **dsh-toolkit 那边的复制品会由另一份任务书清掉** —— 你不用动那个仓库，
   但要保证本仓库清完之后能独立撑起来

---

## 〇之三 环境事实

| 项 | 值 |
|---|---|
| Python | `E:\anaconda\python.exe`（3.12.7），**不要建虚拟环境** |
| 打包 | `E:\anaconda\python.exe tools\build.py` |
| 装到 DSH | `E:\anaconda\python.exe tools\build.py --install C:\Users\X\.dsh\profiles\web` |
| 安装位置 | `C:\Users\X\.dsh\profiles\web\node_modules\dsh-mobile-layout\`（只装了这一个 profile） |
| DSH 本体 | `dsh web` 跑在本机 **19390**；手机端地址走 Tailscale `desktop-h32aemm.tail021ce5.ts.net:8443` |
| 生效条件 | **改完必须重启 `dsh web`** |
| 自检变量 | 插件会往 `window.__DSH_MOBILE_LAYOUT__` 塞 `{ rules, bytes }`（出异常时塞 `{ error }`）—— 这是判断「规则真的进去了吗」的唯一可靠信号。标签存在、文本长度对，都可能是**一段没解析成功的 CSS**（漏一个花括号就够了） |
| shell | **Windows PowerShell 5.1**（不是 pwsh 7）。`.ps1` 必须存成 UTF-8 **带 BOM**；中文输出前先 `[Console]::OutputEncoding=[System.Text.Encoding]::UTF8` |

---

## 一 任务清单

### 任务 1 ★★★ README 开头写死「这个仓库是唯一真源」

现在这个仓库的 README 是一份**很好的技术文档**（它解释了为什么做成插件、
改前改后的实测尺寸、四个 390px 实测出来的数值都是怎么来的）—— **这些一个字都不要删。**

在它**最前面**加一节，标题类似 `## ⚠️ 改这个插件，只改这一个仓库`，内容包括：

1. **一句话**：手机端布局修复插件的唯一真源就是本仓库的 `src/dsh-mobile-fix.css`。
   改完跑 `tools/build.py --install <profile>`，重启 `dsh web` 生效。
2. **把上面那张「四份 CSS / 两条链」的表抄进去**（现在外面还有哪些副本、谁在读），
   并写明：`dsh-toolkit\plugin\` 和 `docs\dsh-mobile-fix.css` 是复制品，**已经删了**；
   `G:\文档\deepseek-harness\default-workspace\dsh-mobile-fix.css` 是历史遗留，不要再改它。
3. **一句最容易踩的**：

   > 改 `dsh-toolkit` 里的任何一份 CSS，手机上都不会变。
   > 真正生效的只有本仓库 `src/dsh-mobile-fix.css` → `tools/build.py --install` 这条路。

4. **`--check` 怎么用**：改完忘了重装的话，跑一下就知道。

★ 如果任务 2 之后 `dsh-toolkit` 那边还留着什么，**以我给的这张表为准**，
  但你实际验证的结果优先 —— **对不上就以你验证的为准，并在进展里说明**。

**验收**：`Get-Content README.md -Encoding UTF8 -TotalCount 40` 的原始输出贴进进展。

---

### 任务 2 ★★★ `tools/build.py` 补成唯一入口：`--profile` + `--check`

现在 `build.py` 的用法是：

```
python tools/build.py                       # 只生成到本仓库的 lib/
python tools/build.py --install <profile>   # 同时装进 profile 的 node_modules
```

**这个设计是对的，保留。** 加两个东西：

1. **`--profile <名字>`**（默认 `web`）
   - 现在 `--install` 要人写一长串完整路径，容易写错，而且**没人知道该装哪个 profile**
     （答案是 `web`，不是 `desktop`）。
   - 支持两种写法：`--profile web`（自动展开成 `C:\Users\X\.dsh\profiles\web`）
     和 `--install <完整路径>`（保留，给非标准位置用）。
   - **把最终安装路径完整打印出来**，别让人猜装哪去了。

2. **`--check`**：比对「仓库 `src/dsh-mobile-fix.css`」和
   「已安装的 `lib/client.js` 里嵌的那段 CSS」是否一致。
   - 一致 → 打印两边长度和哈希前缀，退出码 0
   - 不一致 → 打印**两边都打出来**（长度 + 哈希），说清差在哪，退出码 1
   - 提取嵌入 CSS 的方法：`lib/client.js` 里有 `const CSS = \`...\`;`，
     注意里面的转义（`\\` → `\`、`` \` `` → `` ` ``、`\${` → `${`）——
     **比之前要先把转义解开再比**，否则永远报不一致。
   - 如果插件**根本没装**（profile 里没有这个包），要单独报一句人话，
     不要报成「不一致」。

3. ★ **`--check` 必须能在无人值守下用**：不要有交互式提问，
   不要靠 `input()`，出错就走退出码。

**验收**：
```powershell
E:\anaconda\python.exe tools\build.py --profile web           # 打印装到哪
E:\anaconda\python.exe tools\build.py --check                 # 应报一致
# 故意改一个字节再 check，应该报不一致且退出码 1
E:\anaconda\python.exe tools\build.py --check ; "exit=$LASTEXITCODE"
```
四条命令的**原始输出**都贴进进展。

---

### 任务 3 ★★ 让安装的那份和真源完全一致

现在装的那份和本仓库有差异（`package.json` 多了 `"private": true`，
`lib/client.js` 差 11 行注释）。**这一轮结束时要变成：装的那份就是本仓库产出的那份。**

**做法**：

1. **先备份现有的安装目录**（复制到 `F:\Fendou\projects\dsh-mobile-layout\.backup-installed-<日期>\`，
   加进 `.gitignore`）。理由：万一新装的在手机上表现不一样，要能立刻换回来。
   ★ **是复制，不是移动** —— 装的过程出问题时原状不能被破坏。
2. 跑 `tools\build.py --profile web` 重新装。
3. 装完比对 `lib/client.js` 和 `package.json` 两边的哈希，**打印出来**。
4. **重启 `dsh web`**，然后在浏览器里确认 `window.__DSH_MOBILE_LAYOUT__` 有 `rules` 和 `bytes`
   （**不是** `error`），而且 `rules` 是个正数。
   - 说明：`rules = -1` 表示标签在但 `tag.sheet` 拿不到（可能是跨域/未插入），
     这也算异常，要报出来。
5. 结论写进进展：`rules` 是多少？`bytes` 是多少？和 CSS 文件大小对得上吗？

★ **不要在这条任务里改任何 CSS 规则。** 那些数值（188px 侧栏、36px 高度、46px 开关…）
  都是 390px 实测调出来的，这轮只动打包和安装。

**验收**：`--check` 退出码 0；`window.__DSH_MOBILE_LAYOUT__` 的值贴进进展。

---

### 任务 4 ★★ 给 CSS 加一个「它还是有效的吗」的自检（可选，看时间）

**背景**：这份 CSS 全部用 `[class*='_后缀']` 匹配，因为 DSH 的类名是
`哈希_语义后缀`，哈希每次构建都变、**后缀不变**。这是刻意设计（README 里解释了）。

所以 DSH 普通升级**不会**弄坏它。会弄坏它的是：**后缀改名**、**DOM 层级变了**
（CSS 里大量用 `>`）、或者 **`[role='dialog']` 没了**（全部规则都挂在它下面）。

坏掉的表现是**静默**的：CSS 装上了、不报错、一个元素都没碰到。

**做法**（如果做）：在 `tools/` 下加一个 `check_selectors.py`：

1. 解析 `src/dsh-mobile-fix.css`，把 `@media` 里的每条选择器拆出来
   （注意逗号分隔的多个选择器要拆成独立条目，注释要跳过，**记住行号**）
2. 连上 DSH（Chrome DevTools Protocol），在 390×844 下逐条跑
   `document.querySelectorAll(<选择器>).length`
3. 打印一张表：`第 N 行  选择器  命中 M`，末尾给「命中 X 条 / 零匹配 Y 条」
4. 有零匹配 → 退出码 1

★ 一个诚实要求：如果**全部零匹配**，报告要多说一句人话，因为那几乎肯定不是
  「全部改名了」，而是**页面根本没打开对**：

  > ★★ 全部零匹配 —— 这不像"改版"，更像页面根本没打开对。
  >     先确认：登录了吗？那个"预览版说明"弹窗处理掉了吗？

★ **提示**：`dsh-toolkit` 仓库里有一个 `dsh_mobile_audit.py`，
  它有一段**已经写好并且踩过坑**的逻辑：先点「继续」关掉「预览版说明」弹窗，
  点不掉就把 `[role=dialog]` 里含这几个字的节点从 DOM 摘掉。
  那段注释里写着「第一版就踩了这个：报出'出屏 0'，是假的」。
  **如果你要做这条任务，先去读那段，照着它的做法处理弹窗，不要重写。**
  （另一个仓库正在被另一份任务书改，**你只读、不要动它**。）

**如果这条做不完，不做也行** —— 在进展里说一句「任务 4 未做」即可。
前面三条比它重要。

---

## 二 别碰

1. **`src/dsh-mobile-fix.css` 里的规则内容一个字都不要改。** 这一轮只动打包和文档。
2. **README 里那些实测数据和解释不要删**（改前 342x796 那张尺寸表、
   「为什么要做成插件而不是改 app.asar」、「为什么整段包在 try 里」）——
   那些是这个仓库最值钱的部分。你只在**最前面加**一节。
3. **不要动 `F:\Fendou\projects\dsh-toolkit\`。** 那边由另一份任务书负责，
   你俩同时改会打架。你只读它（任务 4 需要读那段弹窗处理逻辑）。
4. **不要删 `lib/`、`src/`、`cordis.patch.yml`、`package.json` 里的任何东西。**
5. **不要 `git commit`、不要 `git push`。**
6. **不要新建虚拟环境**，不要改 `package.json` 的 `version`。

---

## 三 进展怎么记

每做完一条，把**命令**和**原始输出**（原样复制，不要改写、不要只写「通过」）
追加到 `F:\Fendou\projects\dsh-mobile-layout\进展.md`。末尾写一节 `## 总结`，含：

1. 改了哪些文件（`git status --short` 的原始输出）
2. ★ **所有「任务书和实际代码不一致」的地方** —— 这份任务书是我凭调查写的，
   肯定有写错的地方（尤其那些路径和哈希）。**写错就说写错，不要迁就我。**
   这一节比其它所有节都重要。
3. 你自己拿不准但自己决定了的地方，以及为什么。
4. 哪些验收没跑成、为什么。

---

## 四 做完之后应该是什么样

```powershell
# 一条命令装好，它告诉你装到哪了
E:\anaconda\python.exe tools\build.py --profile web

# 一条命令告诉你「现在装的那份，和仓库里这份，是不是一回事」
E:\anaconda\python.exe tools\build.py --check
#   → 一致，退出码 0

# 打开 README，第一眼就看见「改这个插件只改这一个仓库」
Get-Content README.md -Encoding UTF8 -TotalCount 25

# 手机上打开 DSH，布局还是对的
# 浏览器控制台里 window.__DSH_MOBILE_LAYOUT__ 有 rules 和 bytes
```

**最重要的那条**：下一个人（包括未来的你）想改手机端布局时，
**打开这个仓库就知道该改这里**，
不会再跑去改 `dsh-toolkit` 里那份复制品然后纳闷手机上为什么没变。
