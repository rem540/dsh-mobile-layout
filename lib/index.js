/**
 * dsh-mobile-layout —— 宿主侧。
 *
 * 这个插件纯粹是浏览器侧的样式修正，宿主侧没有任何事情要做。
 * 存在的理由只有一个：cordis.patch.yml 里插入的加载器条目需要一个能被
 * 解析的模块入口，否则宿主启动时会报"条目没能激活"。
 */
export default function mobileLayout() {
  return { name: 'dsh-mobile-layout' };
}
