# -*- coding: utf-8 -*-
"""这份 CSS 还是有效的吗？—— 逐条数命中率。

为什么需要它：`src/dsh-mobile-fix.css` 全部用 `[class*='_后缀']` 匹配，因为
DSH 的类名是 `哈希_语义后缀`，哈希每次构建都变、后缀不变。好处是 DSH 升级
弄不坏它；坏处是**坏掉的时候是静默的** —— CSS 装上了、控制台不报错、
一个元素都没碰到，只有肉眼看手机才会发现"布局又不对了"。

会让它坏掉的三件事（任务书写明的）：
  · 后缀改名（`_navCell` → `_navItem`）
  · DOM 层级变了（CSS 里大量用 `>`）
  · `[role='dialog']` 没了（设置面板那批规则全挂在它下面）

所以要数的是"每条选择器命中了几个元素"，在真页面上数。

用法：
    # 最省事：给一个能打开的地址（带着 token 的那种）
    python tools/check_selectors.py "https://xxx.ts.net:8443/?token=..."

    # 或者给一个存着地址的文件（一行）
    python tools/check_selectors.py --url-file C:\\Users\\X\\.dsh\\dsh-url.txt

    # 或者给环境变量
    set DSH_URL=https://.../?token=...
    python tools/check_selectors.py

不连真页面也可以，自测用本仓库的示例页：
    python tools/check_selectors.py --file tools/sample-dsh.html

退出码：0 = 每条（非伪元素）选择器都至少命中一个；1 = 有零匹配；
       2 = 页面没打开对 / 没有地址（这种情况报的是"页面问题"，不是"CSS 坏了"）。
"""
import argparse
import base64
import json
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CSS = os.path.join(ROOT, 'src', 'dsh-mobile-fix.css')

# 别的机器上 Chrome 可能在别处：先用这几个常见位置，找不到再让用户 --chrome 指。
CHROME_CANDIDATES = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
]


# ══════════════════════════════════════════════════════════════════════
# 一、解析 CSS：把每条选择器和它的行号拆出来
# ══════════════════════════════════════════════════════════════════════
def strip_comments(text):
    """去掉 /* *\\/ 注释，但**把里面的换行原样补回来** —— 行号必须保持对得上。"""
    def repl(m):
        return '\n' * m.group(0).count('\n')
    return re.sub(r'/\*.*?\*/', repl, text, flags=re.S)


def parse_rules(css):
    """返回 ([{line, media, selector, pseudo}], 声明块数)，一层一条选择器。

    · 注释先去掉（行号不变），所以"选择器写在第几行"是真的；
    · `@media (...) { ... }` 里的规则算在 media 上，行号仍是原文行号；
    · 逗号分隔的多个选择器拆成独立条目（任务书要求的）；
    · `::-webkit-scrollbar` 这种伪元素单独标出来 —— 它命中的元素数是 0
      但**不说明任何问题**，不该算进"零匹配"里。
    """
    text = strip_comments(css)
    rules = []
    blocks = 0
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', text):
        sel_raw = m.group(1)
        if not sel_raw.strip():
            continue
        blocks += 1
        line = text.count('\n', 0, m.start(1)) + 1
        # 这条规则是否在某条 @media 里（往前找最近的花括号归属）
        media = None
        head = text[:m.start(1)]
        opens = head.count('{') - head.count('}')
        if opens > 0:
            at = [a for a in re.finditer(r'@media[^{]*', head)]
            if at:
                media = ' '.join(at[-1].group(0).split())
        for sel in sel_raw.split(','):
            sel = ' '.join(sel.split()).strip()
            if not sel:
                continue
            pseudo = bool(re.search(r'::|:(?:hover|active|focus|focus-visible|before|after)\b', sel))
            # 一个声明块里可能有多条选择器分别在不同行，逐条给准确行号
            idx = sel_raw.find(sel.split(' ')[0])
            sub = text.count('\n', 0, m.start(1) + (idx if idx > 0 else 0))
            rules.append({
                'line': line if idx <= 0 else sub + 1,
                'media': media,
                'selector': sel,
                'pseudo': pseudo,
            })
    return rules, blocks


# ══════════════════════════════════════════════════════════════════════
# 二、最小 CDP 客户端（只用标准库，不依赖任何别的仓库）
# ══════════════════════════════════════════════════════════════════════
class WS(object):
    """刚够用的 WebSocket 客户端：握手、发一条文本、收一条（自动拼分片）。"""

    def __init__(self, url, timeout=30):
        assert url.startswith('ws://'), url
        hostport, _, path = url[5:].partition('/')
        host, _, port = hostport.partition(':')
        self.sock = socket.create_connection((host, int(port or 80)), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            'GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\n'
            'Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n'
            'Sec-WebSocket-Version: 13\r\n\r\n' % (path, hostport, key)).encode())
        buf = b''
        while b'\r\n\r\n' not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError('WebSocket 握手时连接被关闭')
            buf += chunk
        head, _, tail = buf.partition(b'\r\n\r\n')
        if b'101' not in head.split(b'\r\n')[0]:
            raise RuntimeError('WebSocket 握手失败：' + head.decode('latin1')[:200])
        self.buf = tail

    def _exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise RuntimeError('连接已关闭')
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text):
        payload = text.encode('utf-8')
        head = bytearray([0x81])
        n = len(payload)
        if n < 126:
            head.append(0x80 | n)
        elif n < (1 << 16):
            head.append(0x80 | 126)
            head += struct.pack('>H', n)
        else:
            head.append(0x80 | 127)
            head += struct.pack('>Q', n)
        mask = os.urandom(4)
        head += mask
        self.sock.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def recv(self):
        data = b''
        while True:
            b0, b1 = self._exact(2)
            fin, opcode, length = b0 & 0x80, b0 & 0x0F, b1 & 0x7F
            if length == 126:
                length = struct.unpack('>H', self._exact(2))[0]
            elif length == 127:
                length = struct.unpack('>Q', self._exact(8))[0]
            mask = self._exact(4) if b1 & 0x80 else None
            payload = self._exact(length)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:
                raise RuntimeError('对端关闭了连接')
            if opcode == 0x9:                       # ping → pong
                self.sock.sendall(b'\x8a\x80' + os.urandom(4))
                continue
            if opcode in (0x1, 0x0):
                data += payload
                if fin:
                    return data.decode('utf-8')

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


class CDP(object):
    def __init__(self, ws_url):
        self.ws = WS(ws_url)
        self.id = 0

    def call(self, method, **params):
        self.id += 1
        mid = self.id
        self.ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == mid:
                if 'error' in msg:
                    raise RuntimeError('%s 失败：%s' % (method, msg['error']))
                return msg.get('result', {})

    def js(self, expr):
        r = self.call('Runtime.evaluate', expression=expr, returnByValue=True)
        res = r.get('result', {})
        if r.get('exceptionDetails'):
            return None
        return res.get('value')

    def wait_for(self, expr, timeout=25, interval=0.3):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if self.js(expr):
                    return True
            except Exception:
                pass
            time.sleep(interval)
        return False

    def close(self):
        self.ws.close()


def find_target(port, timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2) as r:
                for t in json.loads(r.read().decode('utf-8')):
                    if t.get('type') == 'page' and t.get('webSocketDebuggerUrl'):
                        return t['webSocketDebuggerUrl']
        except Exception:
            pass
        time.sleep(0.4)
    raise RuntimeError('没找到可调试的页面（Chrome 起来了吗？端口 %d）' % port)


def find_chrome(explicit=None):
    if explicit:
        return explicit
    for p in CHROME_CANDIDATES:
        if os.path.isfile(p):
            return p
    raise RuntimeError('没找到 Chrome/Edge，用 --chrome "路径" 指一下。')


# ══════════════════════════════════════════════════════════════════════
# 三、弹窗处理 —— 照抄 dsh-toolkit/src/dsh_toolkit/dsh_mobile_audit.py 那段
#     （那段注释写着「第一版就踩了这个：报出'出屏 0'，是假的」）。
#     全新 profile 一定会弹「预览版说明」，它盖住整页；不弄掉的话，
#     量到的是弹窗，主界面的选择器会全部零匹配 —— 而那个"零"是假的。
# ══════════════════════════════════════════════════════════════════════
HIT_JS = r"""
function hit(el){
  var r=el.getBoundingClientRect(), x=r.left+r.width/2, y=r.top+r.height/2;
  ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(t){
    var E=t.indexOf('pointer')===0?PointerEvent:MouseEvent;
    el.dispatchEvent(new E(t,{bubbles:true,cancelable:true,clientX:x,clientY:y,
                              button:0,pointerId:1,isPrimary:true}));
  });
}
"""

DISMISS_JS = HIT_JS + r"""
(function(){
  var c=null;
  document.querySelectorAll('button,[role=button]').forEach(function(b){
    if(!c && /^(继续|知道了|我知道了|开始使用)$/.test((b.getAttribute('aria-label')||b.textContent||'').trim())) c=b;
  });
  if(c) hit(c);
  return c ? 'clicked' : 'none';
})()
"""

REMOVE_DIALOG_JS = r"""
(function(){
  var n=0;
  document.querySelectorAll('[role=dialog]').forEach(function(d){
    var t=(d.textContent||'');
    if(/预览版说明|预览阶段/.test(t)){ d.remove(); n++; }
  });
  return n;
})()
"""

OPEN_SETTINGS_JS = HIT_JS + r"""
(function(){
  function byLabel(re){ var f=null;
    document.querySelectorAll('button,[role=button]').forEach(function(b){
      var lb=(b.getAttribute('aria-label')||b.title||b.textContent||'').trim();
      if(!f&&re.test(lb)) f=b; }); return f; }
  var c=byLabel(/^继续$/); if(c) hit(c);
  var g=byLabel(/^设置$/); if(g) hit(g);
  return g?'ok':'no-gear';
})()
"""

# 数命中：每条选择器单独 try —— ::-webkit-scrollbar 这种伪元素
# querySelectorAll 是能查的（返回 []），但 :has()/新语法在老内核上会抛。
COUNT_JS = r"""
(function(sels){
  var out=[];
  for(var i=0;i<sels.length;i++){
    var s=sels[i], n=-2, err=null;
    try { n = document.querySelectorAll(s).length; }
    catch(e){ n = -1; err = String(e && e.message || e); }
    out.push({n:n, err:err});
  }
  return out;
})(%s)
"""

PAGE_FACTS_JS = r"""(function(){
  var d=document.querySelectorAll('[role=dialog]');
  return {
    url: location.href,
    title: document.title,
    viewport: [innerWidth, innerHeight],
    buttons: document.querySelectorAll('button,[role=button]').length,
    dialogs: d.length,
    dialogText: d.length ? (d[0].textContent||'').replace(/\s+/g,' ').slice(0,48) : null,
    plugin: window.__DSH_MOBILE_LAYOUT__ || null,
    pluginStyle: (function(){
      var t=document.getElementById('dsh-mobile-layout');
      if(!t) return null;
      return {len:(t.textContent||'').length, rules:(t.sheet?t.sheet.cssRules.length:-1)};
    })(),
    dshRoots: document.querySelectorAll('[class*="_panel"],[class*="_nav"],[class*="_frame"]').length
  };
})()"""


# ══════════════════════════════════════════════════════════════════════
# 四、主流程
# ══════════════════════════════════════════════════════════════════════
def resolve_url(args):
    if args.url:
        return args.url
    if args.url_file:
        with open(args.url_file, encoding='utf-8-sig') as f:
            return f.read().strip()
    for env in ('DSH_URL', 'DSH_WEB_URL'):
        if os.environ.get(env):
            return os.environ[env].strip()
    return None


def count_matches(cdp, rules):
    sels = json.dumps([r['selector'] for r in rules])
    res = cdp.js(COUNT_JS % sels)
    if res is None:
        raise RuntimeError('数命中时页面执行出错（页面还在吗？）')
    return res


def report(rules, counts, title):
    zero, bad, pseudo_zero = [], [], []
    print('')
    print('  第 N 行  选择器                                                     命中')
    print('  ' + '-' * 86)
    for r, c in zip(rules, counts):
        n = c['n']
        if n == -1:
            mark = '不合法/不支持'
            bad.append(r)
        elif n == 0 and r['pseudo']:
            mark = '0（伪元素，正常）'
            pseudo_zero.append(r)
        elif n == 0:
            mark = '0  ← 零匹配'
            zero.append(r)
        else:
            mark = str(n)
        sel = r['selector']
        if len(sel) > 62:
            sel = sel[:59] + '...'
        print('  %-8s %-64s %s' % ('第 %d 行' % r['line'], sel, mark))
    total = len(rules)
    tested = total - len(pseudo_zero)
    hit = tested - len(zero) - len(bad)
    print('')
    print('  %s：命中 %d 条 / 零匹配 %d 条（另有 %d 条伪元素不计）'
          % (title, hit, len(zero) + len(bad), len(pseudo_zero)))
    if zero or bad:
        for r in zero + bad:
            print('    · 第 %d 行  %s' % (r['line'], r['selector']))
    return zero, bad, pseudo_zero


def main():
    ap = argparse.ArgumentParser(description='逐条数 CSS 选择器在真 DSH 页面上的命中率')
    ap.add_argument('url', nargs='?', help='DSH 页面地址（带 token 的那种）')
    ap.add_argument('--url-file', help='存着地址的文件（一行）')
    ap.add_argument('--file', help='本地 HTML 文件（不连 DSH，自测用）')
    ap.add_argument('--css', default=CSS, help='要检查的 CSS（默认 src/dsh-mobile-fix.css）')
    ap.add_argument('--width', type=int, default=390)
    ap.add_argument('--height', type=int, default=844)
    ap.add_argument('--chrome', help='chrome.exe / msedge.exe 的路径')
    ap.add_argument('--port', type=int, default=9377, help='调试端口（撞了就换一个）')
    ap.add_argument('--css-only', action='store_true',
                    help='只解析 CSS 并打印拆出来的选择器，不开浏览器（自测/离线看）')
    ap.add_argument('--no-settings', action='store_true',
                    help='不点开设置面板（默认会点开再数一遍：大多数规则挂在 [role=dialog] 下）')
    ap.add_argument('--json', help='把结果另存成 JSON')
    args = ap.parse_args()

    with open(args.css, encoding='utf-8') as f:
        css = f.read()
    rules, blocks = parse_rules(css)
    if not rules:
        print('没从 %s 里解析出任何选择器 —— 是不是路径给错了？' % args.css)
        return 2

    if args.css_only:
        print('%s：%d 个声明块，拆出 %d 条选择器' % (args.css, blocks, len(rules)))
        for r in rules:
            print('  第 %-4d 行 %-8s %s' % (r['line'], '(伪元素)' if r['pseudo'] else '',
                                            r['selector']))
        return 0

    url = resolve_url(args)
    if not url and not args.file:
        print('★ 没有页面地址，什么也数不了。给一个，任选其一：')
        print('    python tools/check_selectors.py "https://<主机>:8443/?token=..."')
        print('    python tools/check_selectors.py --url-file <存着地址的文件>')
        print('    set DSH_URL=... 再跑')
        return 2
    if args.file:
        url = 'file:///' + os.path.abspath(args.file).replace('\\', '/')

    chrome = find_chrome(args.chrome)
    profile = tempfile.mkdtemp(prefix='cdp-mobile-sel-')
    proc = subprocess.Popen([
        chrome, '--headless=new', '--remote-debugging-port=%d' % args.port,
        '--user-data-dir=%s' % profile, '--no-first-run', '--no-default-browser-check',
        '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
        '--window-size=%d,%d' % (args.width, args.height), 'about:blank',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    result = {'url': url, 'css': args.css, 'rules': len(rules), 'phases': {}}
    try:
        cdp = CDP(find_target(args.port))
        cdp.call('Page.enable')
        cdp.call('Runtime.enable')
        cdp.call('Emulation.setDeviceMetricsOverride',
                 width=args.width, height=args.height, deviceScaleFactor=1,
                 mobile=(args.width < 700))
        cdp.call('Page.navigate', url=url)
        cdp.wait_for("document.readyState==='complete'", timeout=45)
        cdp.wait_for("document.querySelectorAll('button,[role=button]').length > 3", timeout=45)
        cdp.wait_for('1', timeout=2)

        print('页面：%s' % url)
        print('CSS ：%s（%d 个声明块 / %d 条选择器）' % (args.css, blocks, len(rules)))

        facts = cdp.js(PAGE_FACTS_JS) or {}
        result['page'] = facts
        print('  viewport=%s  按钮=%s  [role=dialog]=%s  DSH 根元素=%s'
              % (facts.get('viewport'), facts.get('buttons'),
                 facts.get('dialogs'), facts.get('dshRoots')))
        print('  window.__DSH_MOBILE_LAYOUT__ = %s' % json.dumps(facts.get('plugin')))

        # ── 阶段 1：主界面。先按 dsh_mobile_audit.py 的做法关掉「预览版说明」。
        print('')
        print('  [弹窗] 点「继续」：%s' % (cdp.js(DISMISS_JS) or '(没找到)'))
        cdp.wait_for('1', timeout=2)
        print('  [弹窗] 兜底从 DOM 摘掉含「预览版说明」的 [role=dialog]：%s 个'
              % (cdp.js(REMOVE_DIALOG_JS)))
        cdp.wait_for('1', timeout=2)
        counts = count_matches(cdp, rules)
        result['phases']['main'] = {r['selector']: c['n'] for r, c in zip(rules, counts)}
        zero_main, bad_main, pseudo_main = report(rules, counts, '主界面（未开设置）')

        zero_settings, bad_settings, pseudo_settings = [], [], []
        if not args.no_settings:
            print('')
            print('  [设置] 点开设置面板：%s' % (cdp.js(OPEN_SETTINGS_JS) or '(没返回)'))
            cdp.wait_for("document.querySelector('[role=dialog]') ? 1 : 0", timeout=15)
            cdp.wait_for('1', timeout=3)
            counts2 = count_matches(cdp, rules)
            result['phases']['settings'] = {r['selector']: c['n'] for r, c in zip(rules, counts2)}
            zero_settings, bad_settings, pseudo_settings = report(rules, counts2, '设置面板打开后')

        # 结论：同一条选择器**两个阶段都没命中**才算零匹配 ——
        # 有的规则只对主界面生效（_rightbarCol），有的只对设置面板生效（_navCell）。
        worst = []
        for i, r in enumerate(rules):
            if r['pseudo']:
                continue
            ns = [result['phases'][p][r['selector']] for p in result['phases']]
            if all(n == 0 for n in ns):
                worst.append(r)
            if any(n == -1 for n in ns) and r not in worst:
                worst.append(r)

        print('')
        print('  ══════ 结论 ══════')
        print('  两个阶段都没命中的选择器：%d 条' % len(worst))
        for r in worst:
            print('    · 第 %d 行  %s' % (r['line'], r['selector']))

        all_zero = len(worst) == len([r for r in rules if not r['pseudo']])
        if all_zero:
            # ★ 任务书要求的那句人话，一个字都别省：
            print('')
            print('  ★★ 全部零匹配 —— 这不像"改版"，更像页面根本没打开对。')
            print('     先确认：登录了吗？那个"预览版说明"弹窗处理掉了吗？')
            print('     （判据：页面按钮数 %s、DSH 根元素 %s —— 都是 0 就是没登录/没加载）'
                  % (facts.get('buttons'), facts.get('dshRoots')))
        elif worst:
            print('')
            print('  这些选择器在真页面上一个元素都没碰到。坏掉的表现本来就是静默的，')
            print('  先照上面每条确认：后缀改名了？DOM 层级变了？[role=dialog] 没了？')

        code = 0 if not worst else 1
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print('')
        print('  JSON 已写到 %s' % args.json)
    print('')
    print('  退出码 %d' % code)
    return code


if __name__ == '__main__':
    sys.exit(main())
