/* Global ambient declarations for claw-delivery-ui */

/** Vite `?raw` 导入：把 .html 当作字符串引入（用于 iframe srcDoc 嵌入登录页等） */
declare module '*.html?raw' {
  const src: string;
  export default src;
}

declare module '*.svg' {
  const src: string;
  export default src;
}

/**
 * Shorthand 声明：让 xlsx / mammoth 在「尚未 npm install」时也能通过模块解析
 * （SduiPreviewModal 走动态 import + 本地最小接口断言，不依赖这两个库自带类型）。
 * npm install xlsx mammoth 之后，库自带类型存在；本地断言仍生效，运行行为不变。
 */
declare module 'xlsx';
declare module 'mammoth';
