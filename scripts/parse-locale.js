// 用 TypeScript 编译器 API 精确解析 locale 文件，输出扁平键值对
// 用法: node parse-locale.js <file.ts> <out.json>
const fs = require("fs");
const path = require("path");

const file = process.argv[2];
const outPath = process.argv[3];

// 定位 typescript 模块：环境变量 > Hermes 安装目录 > 文件所在树 > 全局
const candidateRoots = [
  process.env.HERMES_TYPESCRIPT,
  path.join(process.env.HERMES_DIR || "/opt/hermes", "node_modules", "typescript"),
  path.join(path.dirname(file), "..", "..", "..", "node_modules", "typescript"),
  "typescript",
].filter(Boolean);

let ts = null;
for (const p of candidateRoots) {
  try {
    const m = require(p);
    // TypeScript 7.x 的包结构变了：编译器挂在 default 或具名导出上
    const cand = (m && typeof m.createSourceFile === "function") ? m
               : (m && m.default && typeof m.default.createSourceFile === "function") ? m.default
               : null;
    if (cand) { ts = cand; break; }
  } catch (e) { /* 继续尝试下一个 */ }
}
if (!ts) {
  console.error("找不到可用的 typescript 模块（需要 5.x，7.x 请用 default 导出）。");
  process.exit(1);
}

const src = fs.readFileSync(file, "utf8");
const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);

const result = {};
const LOCALE_VARS = new Set(["en", "zh", "zhHant", "ja", "ko", "de", "fr", "es", "ru"]);

function keyName(node) {
  if (!node) return null;
  if (ts.isIdentifier(node)) return node.text;
  if (ts.isStringLiteral(node)) return node.text;
  return null;
}

function walk(node, prefix) {
  if (!ts.isObjectLiteralExpression(node)) return;
  for (const prop of node.properties) {
    if (!ts.isPropertyAssignment(prop)) continue;
    const k = keyName(prop.name);
    if (!k) continue;
    const full = prefix ? `${prefix}.${k}` : k;
    const init = prop.initializer;

    if (ts.isObjectLiteralExpression(init)) {
      walk(init, full);
      continue;
    }
    if (ts.isStringLiteral(init) || ts.isNoSubstitutionTemplateLiteral(init)) {
      result[full] = init.text;
      continue;
    }
    if (ts.isTemplateExpression(init)) {
      let s = init.head.text;
      for (const span of init.templateSpans) {
        s += "${" + span.expression.getText(sf) + "}" + span.literal.text;
      }
      result[full] = s;
      continue;
    }
    if (ts.isParenthesizedExpression(init) && ts.isStringLiteral(init.expression)) {
      result[full] = init.expression.text;
    }
  }
}

function visit(node) {
  if (ts.isVariableDeclaration(node) && node.initializer &&
      ts.isObjectLiteralExpression(node.initializer)) {
    const nm = keyName(node.name);
    if (LOCALE_VARS.has(nm)) walk(node.initializer, "");
  }
  ts.forEachChild(node, visit);
}
visit(sf);

fs.writeFileSync(outPath, JSON.stringify(result, null, 2), "utf8");
const keys = Object.keys(result);
console.log(`parsed ${path.basename(file)}: ${keys.length} keys (ui.*: ${keys.filter(k => k.startsWith("ui.")).length})`);