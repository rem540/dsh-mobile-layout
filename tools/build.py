# -*- coding: utf-8 -*-
"""把 src/dsh-mobile-fix.css 打包成 DSH 客户端插件 dsh-mobile-layout。

为什么要做成插件而不是改 app.asar：asar 里改一个文件要重建上万个文件的索引，
而且 DSH 一升级就没了。DSH 有官方的客户端插件机制（客户端入口用
window.__ModuleLoader__.load 注册，宿主按包的 dsh.client 声明把它挂在
/plugins/<包名>/client.js）。

这个脚本让 CSS 只有一份真源：改完 src/dsh-mobile-fix.css 重跑它即可。

用法：
    python tools/build.py                 # 只生成到本仓库的 lib/
    python tools/build.py --profile web   # 装进 ~/.dsh/profiles/web（默认 profile 就叫 web）
                                          #     最终安装路径会完整打印出来
    python tools/build.py --install <目录>  # 非标准位置：装进 <目录>/node_modules/dsh-mobile-layout
    python tools/build.py --check         # 只比对不写文件：真源和已安装 lib/client.js 里嵌的 CSS
                                          #     一致退出码 0，不一致退出码 1；没装则单独报一句
                                          #     可与 --profile/--install 连用指定查哪个 profile
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src', 'dsh-mobile-fix.css')
PLUGIN_ID = 'dsh-mobile-layout'
DEFAULT_PROFILE = 'web'

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


def write_tree(base, files, label, only_changed=False):
    """把 files 写进 base。only_changed=True 时内容相同的文件不重写。

    only_changed 不是为了省事：**已经跑着的 dsh web 是启动时扫描插件的**，
    内容没变也去重写一遍文件，就把"跑着的那份到底是不是这份"变成了未知数 ——
    只能靠重启来消掉这个疑问。内容相同的文件保持原样，mtime 不动，
    "刚装过"和"装的是同一份"这两件事就不会互相污染。
    """
    print('%s: %s' % (label, base))
    for rel, text in files.items():
        p = os.path.join(base, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        note = ''
        if only_changed and os.path.isfile(p):
            with open(p, encoding='utf-8') as f:
                if f.read() == text:
                    print('  same  %-24s %6d bytes (没变，不重写)'
                          % (rel, len(text.encode('utf-8'))))
                    continue
            note = ' (内容有变)'
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print('  wrote %-24s %6d bytes%s' % (rel, len(text.encode('utf-8')), note))


def selfcheck(files):
    json.loads(files['package.json'])
    body = files['lib/client.js']
    assert '%(' not in body, 'CLIENT_TEMPLATE 里有没被替换的占位符'
    assert 'window.__ModuleLoader__.load' in body
    print('ok: package.json 可解析, client.js 无残留占位符')


def profile_dir(name):
    """--profile 的名字展开成 DSH profile 目录：~/.dsh/profiles/<名字>。"""
    return os.path.join(os.path.expanduser('~'), '.dsh', 'profiles', name)


def extract_embedded_css(client_js):
    """从生成的 lib/client.js 里把模板字符串里的 CSS 抠出来，并反转义。

    render() 对 CSS 做了三步转义（按顺序）：\\ -> \\\\、` -> \\`、${ -> \\${。
    这里按逆序解回来；比之前不解开会永远报"不一致"。
    """
    m = re.search(r'const CSS = `(.*?)`;', client_js, re.S)
    if not m:
        raise ValueError('找不到 `const CSS = `...`;`，这不像本仓库 build.py 生成的 client.js')
    t = m.group(1)
    t = t.replace('\\${', '${')
    t = t.replace('\\`', '`')
    t = t.replace('\\\\', '\\')
    return t


def check(probe, how):
    """比对真源 src/dsh-mobile-fix.css 和已装在 <probe> 的 lib/client.js 里嵌的 CSS。

    <how> 是"这个 <probe> 是怎么来的"的人话（`--profile web` / `--install <路径>`），
    报"没装"时要把它说回去 —— 否则照抄 DEFAULT_PROFILE 会指错地方。

    返回进程退出码：一致 0；不一致 1；没装也是 1，但报的是"没装"，不是"不一致"。
    """
    with open(SRC, encoding='utf-8') as f:
        src = f.read()
    pkg = os.path.join(probe, 'node_modules', PLUGIN_ID)
    client = os.path.join(pkg, 'lib', 'client.js')
    if not os.path.isfile(client):
        print('插件没装：%s 下没有 %s。' % (probe, PLUGIN_ID))
        print('  这不是"不一致"，是那份压根不存在 —— 先装：'
              'python tools/build.py %s' % how)
        return 1
    with open(client, encoding='utf-8') as f:
        js = f.read()
    try:
        installed = extract_embedded_css(js)
    except ValueError as err:
        print('装的那份 %s 有点不对劲：%s' % (client, err))
        return 1

    src_b = src.encode('utf-8')
    ins_b = installed.encode('utf-8')
    hs = hashlib.sha256(src_b).hexdigest()
    hi = hashlib.sha256(ins_b).hexdigest()
    if installed == src:
        print('一致：真源 %s %d bytes (sha256 %s...)'
              % (os.path.relpath(SRC, ROOT), len(src_b), hs[:16]))
        print('      已装 %s 内嵌 CSS %d bytes (sha256 %s...)'
              % (client, len(ins_b), hi[:16]))
        print('      （对比的是解开 \\\\ \\` \\${ 转义之后的 CSS，不是文件字节）')
        return 0

    # 不一致：两边都打出来，并指出第一处不同在哪
    print('不一致：')
    print('  真源 %s %d bytes (sha256 %s...)' % (os.path.relpath(SRC, ROOT), len(src_b), hs[:16]))
    print('  已装 %s 内嵌 CSS %d bytes (sha256 %s...)' % (client, len(ins_b), hi[:16]))
    n = min(len(src), len(installed))
    i = next((k for k in range(n) if src[k] != installed[k]), n)
    if i == n and len(src) != len(installed):
        print('  前 %d 个字符都一样，长度不同（真源 %d / 已装 %d）'
              % (n, len(src), len(installed)))
    else:
        line = src.count('\n', 0, i) + 1
        print('  第一处不同在真源第 %d 行附近（字符 %d）' % (line, i))
        print('    真源：%s' % src[max(0, i - 30):i + 30].replace('\n', '\\n'))
        print('    已装：%s' % installed[max(0, i - 30):i + 30].replace('\n', '\\n'))
    print('  修：python tools/build.py %s' % how)
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', metavar='NAME',
                    help='DSH profile 名（默认是 %s，不是 desktop）。自动展开成 '
                         '~/.dsh/profiles/<NAME>，比如 --profile web 装到 %s。'
                         '给了就安装。' % (DEFAULT_PROFILE, profile_dir(DEFAULT_PROFILE)))
    ap.add_argument('--install', metavar='PROFILE_DIR',
                    help='DSH profile 目录（如 ~/.dsh/profiles/web）。非标准位置才用，'
                         '给了就装到 <PROFILE_DIR>/node_modules/dsh-mobile-layout')
    ap.add_argument('--check', action='store_true',
                    help='只比对、不写任何文件：真源 src/dsh-mobile-fix.css 和已安装的 '
                         'lib/client.js 里嵌的 CSS 是否一致。一致退出码 0，不一致退出码 1，'
                         '没装单独报一句（也是退出码 1）。默认查 %s profile，'
                         '可用 --profile/--install 指定别的。全程无交互，可无人值守。'
                         % DEFAULT_PROFILE)
    ap.add_argument('-q', '--quiet', action='store_true',
                    help='安静模式：只打结论，不打每个文件的字节数。')
    args = ap.parse_args()

    # --check 与 --install 同时给的时候以 --install 为准（下面两处都走同一个顺序）。
    if args.install:
        target = os.path.abspath(args.install)
        how = '--install "%s"' % target
    elif args.profile:
        target = profile_dir(args.profile)
        how = '--profile %s' % args.profile
    else:
        target = None
        how = '--profile %s' % DEFAULT_PROFILE

    with open(SRC, encoding='utf-8') as f:
        css = f.read()
    files = render(css)

    if args.check:
        # ★ 纯查询：一个文件都不写（包括本仓库的 lib/）。
        #   原来这里先 write_tree(ROOT) 再比 —— 那让 --check 顺手改了仓库产物，
        #   而 --check 的全部意义就是"我现在装的和仓库里这份是不是一回事"。
        probe = target if target else profile_dir(DEFAULT_PROFILE)
        print('仓库真源：%s' % SRC)
        print('安装位置：%s' % os.path.join(probe, 'node_modules', PLUGIN_ID))
        if not args.quiet:
            write_tree(ROOT, files, 'repo (只报不改：--check 不写文件)', only_changed=True)
        sys.exit(check(probe, how))

    root_written = write_tree(ROOT, files, 'repo')
    selfcheck(files)
    del root_written

    if target:
        dest = os.path.join(target, 'node_modules', PLUGIN_ID)
        # 先清掉旧产物：lib/ 里残留的旧文件会被 DSH 一起加载。
        # 注意 dest 是 profile 目录拼出来的，profile 名不该带 .. —— 清之前先确认它
        # 确实在 <target>/node_modules 下面，别让一个手滑的 profile 名删掉别的东西。
        parent = os.path.join(target, 'node_modules')
        if os.path.commonpath([os.path.abspath(dest), os.path.abspath(parent)]) != os.path.abspath(parent):
            sys.exit('拒绝安装：%s 不在 %s 下面' % (dest, parent))
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        write_tree(dest, files, 'install', only_changed=False)
        print('安装路径：%s' % dest)
        print('装好了。重启 dsh web 生效。')
    elif not args.quiet:
        print('没给 --profile/--install，只更新了本仓库的 lib/。'
              '要装进 DSH：python tools/build.py --profile %s' % DEFAULT_PROFILE)


if __name__ == '__main__':
    main()
