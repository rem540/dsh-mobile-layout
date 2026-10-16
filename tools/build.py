# -*- coding: utf-8 -*-
"""把 src/dsh-mobile-fix.css 打包成 DSH 客户端插件 dsh-mobile-layout。

为什么要做成插件而不是改 app.asar：asar 里改一个文件要重建上万个文件的索引，
而且 DSH 一升级就没了。DSH 有官方的客户端插件机制（客户端入口用
window.__ModuleLoader__.load 注册，宿主按包的 dsh.client 声明把它挂在
/plugins/<包名>/client.js）。

这个脚本让 CSS 只有一份真源：改完 src/dsh-mobile-fix.css 重跑它即可。

用法：
    python tools/build.py                       # 只生成到本仓库的 lib/
    python tools/build.py --install <profile>   # 同时装进 DSH profile 的 node_modules
                                                # 例如 --install C:\\Users\\me\\.dsh\\profiles\\web
"""
import argparse
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src', 'dsh-mobile-fix.css')
PLUGIN_ID = 'dsh-mobile-layout'

PACKAGE_JSON = {
    "name": PLUGIN_ID,
    "version": "1.0.0",
    "description": "窄屏下修 DSH 设置面板的布局：侧栏折叠成顶部标签条，设置项换行排版。",
    "type": "module",
    "main": "lib/index.js",
    "exports": {
        ".": {"default": "./lib/index.js"},
        "./client": {"default": "./lib/client.js"},
        "./package.json": "./package.json",
    },
    "files": ["lib", "cordis.patch.yml"],
    "dsh": {
        "bundle": {"patch": "./cordis.patch.yml"},
        "client": {
            # 只声明真正依赖的种子包。别的皮肤插件会声明好几个，是因为它们
            # 要改主题和设置页；这个插件只往 <head> 塞一个 <style>，不 require
            # 任何东西，所以 inject 留空数组 —— 声明得越多，将来 DSH 改版
            # 时被牵动的面越大。
            "inject": [],
            "platform": "web",
            "immediately": True,
        },
    },
}

CORDIS_PATCH = """# dsh-mobile-layout profile patch layer
# 往加载器里插一条条目；浏览器那一半由 dsh-client-modules 通过包的
# dsh.client 声明自动挂到 /plugins/dsh-mobile-layout/client.js。
- insert:
    - id: mobile-layout
      name: 'dsh-mobile-layout'
"""

# 宿主侧那一半：这个插件没有后端需求，但加载器条目需要一个模块能被 require。
HOST_INDEX = """/**
 * dsh-mobile-layout —— 宿主侧。
 *
 * 这个插件纯粹是浏览器侧的样式修正，宿主侧没有任何事情要做。
 * 存在的理由只有一个：cordis.patch.yml 里插入的加载器条目需要一个能被
 * 解析的模块入口，否则宿主启动时会报"条目没能激活"。
 */
export default function mobileLayout() {
  return { name: 'dsh-mobile-layout' };
}
"""

CLIENT_TEMPLATE = """// dsh-mobile-layout —— 浏览器侧。
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

const CSS = %(css)s;

window.__ModuleLoader__.load({
  id: '%(id)s',
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
          tag.dataset.plugin = '%(id)s';
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
"""


def render(css):
    """把 CSS 嵌进 JS 模板字符串，返回 {相对路径: 文本}。"""
    js_css = css.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
    return {
        'package.json': json.dumps(PACKAGE_JSON, indent=2, ensure_ascii=False) + '\n',
        'cordis.patch.yml': CORDIS_PATCH,
        'lib/index.js': HOST_INDEX,
        'lib/client.js': CLIENT_TEMPLATE % {'css': '`' + js_css + '`', 'id': PLUGIN_ID},
    }


def write_tree(base, files, label):
    print('%s: %s' % (label, base))
    for rel, text in files.items():
        p = os.path.join(base, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print('  wrote %-24s %6d bytes' % (rel, len(text.encode('utf-8'))))


def selfcheck(files):
    json.loads(files['package.json'])
    body = files['lib/client.js']
    assert '%(' not in body, 'CLIENT_TEMPLATE 里有没被替换的占位符'
    assert 'window.__ModuleLoader__.load' in body
    print('ok: package.json 可解析, client.js 无残留占位符')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--install', metavar='PROFILE_DIR',
                    help='DSH profile 目录（如 ~/.dsh/profiles/web）。给了就同时装到 '
                         '<PROFILE_DIR>/node_modules/dsh-mobile-layout')
    args = ap.parse_args()

    with open(SRC, encoding='utf-8') as f:
        css = f.read()
    files = render(css)

    write_tree(ROOT, files, 'repo')
    selfcheck(files)

    if args.install:
        dest = os.path.join(os.path.abspath(args.install), 'node_modules', PLUGIN_ID)
        # 先清掉旧产物：lib/ 里残留的旧文件会被 DSH 一起加载
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        write_tree(dest, files, 'install')
        print('装好了。重启 dsh web 生效。')


if __name__ == '__main__':
    main()
