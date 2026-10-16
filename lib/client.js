// dsh-mobile-layout —— 浏览器侧。
//
// 由 dsh-client-modules 挂在 /plugins/dsh-mobile-layout/client.js，
// 经 window.__ModuleLoader__.load 注册（和 DSH 自带的 ui-* 包同一条路径）。
//
// 做的事只有一件：往 <head> 塞一个 <style>，在窄屏下修设置面板的排版。
// 不 require 任何东西、不碰 cordis 的上下文 —— 少一个依赖就少一种
// 随 DSH 升级而失效的方式。
//
// 为什么整段都包在 try 里：加载器条目的工厂函数一旦抛异常，会聚合进
// "entries did not activate"，把整个 web shell 拖下水。一个改样式的插件
// 绝不该有这个本事。
//
// 本文件由 tools/build.py 从 src/dsh-mobile-fix.css 生成。别直接改这里。

const CSS = `/* DSH 手机端布局修复（第二版：按真实 DOM 结构精确锚定）
 *
 * 改前的病根（390px 实测）：
 *   .wCInkW_panel   [342x796] disp=flex dir=row
 *     nav.wCInkW_nav[188x796] disp=flex dir=column   <- 侧栏固定 188px
 *     .wCInkW_content[154x796]                        <- 只剩 154px
 *       .wCInkW_options[154x742] 内边距后内容仅 106px
 *         .Hefa_q_row [106x77] disp=flex dir=row wrap=nowrap
 *           .Hefa_q_rowText[48x44] flex=1/1/0%
 *             .Hefa_q_title[0x44]  <- 标题宽度被算成 0，"语言"竖成一列
 *
 * 第一版为什么把面板改空了：用 \`[class*="_nav"]\` 这种子串选择器，
 * 它同时命中了 .wCInkW_navList / _navCell / _navTitle —— 把本该竖排的
 * 列表强行改成横排，整个导航塌了。所以这一版：
 *   · 只用元素标签锚定侧栏（\`nav[class*="_nav"]\`，全页面只有它一个是 <nav>）
 *   · 其余选择器一律带上"必须是某个父元素的直接子元素"（\`>\`）来收窄
 *   · 需要"选中行的容器"时用 \`:has(> …)\`（CSS 没有父选择器，
 *     而 \`[class*="_row"]\` 会连 \`_rowText\` 一起匹配，分不开）
 *
 * class 名是 CSS Modules 生成的"哈希_语义后缀"，哈希随构建变、后缀不变，
 * 所以这里只匹配后缀。
 */

@media (max-width: 700px) {
  /* ── 1. 面板：左右两栏改成上下两段，并占满整屏 ───────────────────
     注意：[role=dialog] 这个元素**本身就是** .wCInkW_panel（不是它的子元素），
     第一版写成 \`[role='dialog'] > [class*='_panel']\` 于是全场零匹配。 */
  [role='dialog'][class*='_panel'] {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    max-width: 100vw !important;
    height: 100vh !important;
    height: 100dvh !important;
    max-height: 100vh !important;
    max-height: 100dvh !important;
    margin: 0 !important;
    border-radius: 0 !important;
    flex-direction: column !important;
  }

  /* ── 2. 侧栏 → 顶部横向标签条（可横滑） ───────────────────────── */
  [role='dialog'] > nav[class*='_nav'] {
    flex: 0 0 auto !important;
    width: 100% !important;
    height: auto !important;
    max-height: none !important;
    flex-direction: row !important;
    align-items: center !important;
    overflow-x: auto !important;
    overflow-y: hidden !important;
    border-right: 0 !important;
    scrollbar-width: none;
  }
  [role='dialog'] nav[class*='_nav']::-webkit-scrollbar { display: none; }

  /* "设置"这个标题在横排里白占一行，手机上省掉 */
  [role='dialog'] nav[class*='_nav'] > [class*='_navTitle'] { display: none !important; }

  [role='dialog'] nav[class*='_nav'] > [class*='_navList'] {
    flex: 1 1 auto !important;
    flex-direction: row !important;
    width: 100% !important;
    height: auto !important;
  }
  [role='dialog'] nav[class*='_nav'] [class*='_navCell'] {
    flex: 0 0 auto !important;
    width: auto !important;
    height: 36px !important;
    padding: 0 12px !important;
  }
  [role='dialog'] nav[class*='_nav'] [class*='_navLabel'] {
    flex: 0 0 auto !important;
    min-width: 0 !important;
    white-space: nowrap !important;
    overflow: visible !important;
    text-overflow: clip !important;
  }

  /* ── 3. 内容区接住剩下的高度 ──────────────────────────────────── */
  [role='dialog'] > [class*='_content'] {
    flex: 1 1 auto !important;
    width: 100% !important;
    min-width: 0 !important;
    min-height: 0 !important;
  }

  /* ── 4. 设置行：文字占满一整行，控件换行到下面 ───────────────────
     这里刻意**不**只认 \`_rowText\`：\`PgWN5G_row\` 的第一个孩子是个没有
     该类的裸 <div>，只认类名会漏掉它。所以统一让"每一行的第一个孩子"
     占满整行，无论它叫什么。 */
  [role='dialog'] [class*='_row'],
  [role='dialog'] [class*='_setting'] {
    flex-wrap: wrap !important;
    align-items: flex-start !important;
    row-gap: 8px !important;
  }
  [role='dialog'] [class*='_row'] > :first-child,
  [role='dialog'] [class*='_setting'] > :first-child,
  [role='dialog'] [class*='_rowText'],
  [role='dialog'] [class*='_settingText'] {
    flex: 1 1 100% !important;
    width: 100% !important;
    min-width: 0 !important;
  }
  /* 标题/描述本身也要允许收缩，否则它们仍会被算成 0 宽 */
  [role='dialog'] [class*='_rowText'] > *,
  [role='dialog'] [class*='_settingText'] > *,
  [role='dialog'] [class*='_title'],
  [role='dialog'] [class*='_desc'],
  [role='dialog'] [class*='_description'] {
    min-width: 0 !important;
    white-space: normal !important;
    overflow-wrap: anywhere !important;
  }

  /* ── 5. 外观的三个主题方块：手机上排成一行 ────────────────────── */
  [role='dialog'] [class*='_cubeRow'] {
    flex-wrap: wrap !important;
    gap: 8px !important;
  }
  [role='dialog'] [class*='_cubeRow'] > * {
    flex: 1 1 88px !important;
    min-width: 0 !important;
  }

  /* ── 6. 把过小的点击目标撑到手指够得着 ─────────────────────────
     体检（dsh_mobile_audit.py）实测：字号加减的上下箭头各 17x12，
     开关 36x20。桌面用鼠标没问题，手指按 12px 高的目标基本按不准。
     只放大热区与控件本身，不改视觉风格。 */
  [role='dialog'] [class*='_arrows'] {
    min-width: 32px !important;
    min-height: 48px !important;
    justify-content: center !important;
  }
  [role='dialog'] [class*='_arrows'] > * {
    min-height: 24px !important;
    width: 100% !important;
  }
  [role='dialog'] [class*='_switch'] {
    min-width: 46px !important;
    min-height: 28px !important;
  }
}

/* ══════════════════════════════════════════════════════════════════════
   7. 右栏被压成 0 宽时，别让它的内容继续按 390px 布局        （主界面）
   ══════════════════════════════════════════════════════════════════════
   实测（dsh_probe2.py，390px）：BynINW_frame 是个三栏 grid ——
     _sidebarCol  56px  ✓
     _centerCol  334px  ✓
     _rightbarCol  0px  ← 宽度是 0，但 scrollWidth 仍是 390
   于是 frame 的 scrollWidth = 390 + 390 = 780。外层 overflow-x:hidden
   把它裁掉了，所以**肉眼完全看不出来**，只有量 scrollWidth 才现形 ——
   但东西一直在那儿被布局、被绘制。给它自己加 overflow:hidden，让它成为
   裁剪容器，就不再往父级传导了。
   只限窄屏：宽屏下右栏是真面板，overflow:hidden 会把它的滚动条切掉。 */
@media (max-width: 700px) {
  [class*='_rightbarCol'] {
    overflow: hidden !important;
  }
}

/* ══════════════════════════════════════════════════════════════════════
   8. 设置顶部的标签条：宁可换行，也不要横滑                （设置面板）
   ══════════════════════════════════════════════════════════════════════
   实测四个标签 104 + 76 + 104 + 117 = 401px，加间距 413，而可用只有
   366 —— 于是「Agent 预设」被推到屏幕外，要横滑才看得到。滚动条是藏
   起来的，所以用户根本不知道还能往右滑。
   手机上宁可换行：四个标签铺两行全都看得见，比"最后一个藏在外面"强。
   同时把内边距从 12 收到 10，尽量让它们挤在一行里（挤不下才换行）。 */
@media (max-width: 700px) {
  [role='dialog'] nav[class*='_nav'] > [class*='_navList'] {
    flex-wrap: wrap !important;
    row-gap: 4px !important;
    overflow-x: visible !important;
  }
  [role='dialog'] nav[class*='_nav'] [class*='_navCell'] {
    padding: 0 10px !important;
  }
}
`;

window.__ModuleLoader__.load({
  id: 'dsh-mobile-layout',
  factory: () => {
    const module = { exports: {} };
    const exports = module.exports;
    Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });

    const STYLE_ID = 'dsh-mobile-layout';

    function apply() {
      try {
        let tag = document.getElementById(STYLE_ID);
        if (!tag) {
          tag = document.createElement('style');
          tag.id = STYLE_ID;
          tag.dataset.plugin = 'dsh-mobile-layout';
          document.head.appendChild(tag);
        }
        if (tag.textContent !== CSS) tag.textContent = CSS;
        const n = tag.sheet ? tag.sheet.cssRules.length : -1;
        // 只认"规则进去了"：标签存在、文本长度对，都可能是一段没解析成功的
        // CSS（漏一个花括号就够了 —— 标签在、长度对、规则 0 条，而人会对着
        // 没变的尺寸反复调选择器）。
        window.__DSH_MOBILE_LAYOUT__ = { rules: n, bytes: CSS.length };
      } catch (err) {
        window.__DSH_MOBILE_LAYOUT__ = { error: String(err) };
      }
    }

    apply();
    // 样式必须在 DSH 自己的样式表之后才能压过它。插件可能在 shell 样式之前
    // 跑，所以再补两次；用 <style> 而非 CSSStyleSheet.insertRule，因为它天然
    // 排在作者样式表的后面。
    if (document.readyState !== 'complete') {
      document.addEventListener('DOMContentLoaded', apply, { once: true });
      window.addEventListener('load', apply, { once: true });
    }

    exports.apply = apply;
    return module.exports;
  },
});
