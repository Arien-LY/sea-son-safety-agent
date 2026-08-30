const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function loadRenderer() {
  const source = fs.readFileSync(path.join(__dirname, '../src/markdown.ts'), 'utf8');
  const js = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  }).outputText;
  const exports = {};
  new Function('require', 'exports', js)(require, exports);
  return exports.renderAssistantMarkdown;
}

const render = loadRenderer();

test('renders structured markdown with safe line breaks and code', () => {
  const html = render('# 标题\n第一行\n第二行\n\n- **重点**\n- `code`\n\n```js\nalert("text only")\n```');
  assert.match(html, /<h2>标题<\/h2>/);
  assert.match(html, /第一行<br>\n第二行/);
  assert.match(html, /<ul>/);
  assert.match(html, /<strong>重点<\/strong>/);
  assert.match(html, /<code>code<\/code>/);
  assert.match(html, /<pre><code class="language-js">alert\(&quot;text only&quot;\)/);
});

test('escapes raw HTML instead of creating executable elements', () => {
  const html = render('<script>alert(1)</script>\n<img src=x onerror="alert(2)">\n<iframe src="https://evil.example"></iframe>');
  assert.doesNotMatch(html, /<script|<img|<iframe/i);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /onerror=&quot;alert\(2\)&quot;/);
});

test('allows only explicit http https and mailto links with opener protection', () => {
  const html = render([
    '[HTTPS](https://example.com/a?q=1)',
    '[邮件](mailto:safety@example.com)',
    '[脚本](javascript:alert(1))',
    '[混淆脚本](JaVaScRiPt%3Aalert(1))',
    '[文件](file:///etc/passwd)',
    '[数据](data:text/html,boom)',
    '[协议相对](//evil.example/a)',
    '[相对](/admin)',
  ].join('\n'));
  assert.equal((html.match(/<a /g) ?? []).length, 2);
  assert.equal((html.match(/target="_blank"/g) ?? []).length, 2);
  assert.equal((html.match(/rel="noopener noreferrer"/g) ?? []).length, 2);
  assert.doesNotMatch(html, /href="(?:javascript|file|data):|href="\/\//i);
});

test('never loads markdown images and renders only escaped alt text', () => {
  const html = render('![现场<svg onload=alert(1)>](https://tracker.example/pixel.png "secret")');
  assert.doesNotMatch(html, /<img|tracker\.example/i);
  assert.match(html, /class="markdown-image-alt"/);
  assert.match(html, /现场&lt;svg onload=alert\(1\)&gt;/);
});

test('escapes hostile link titles and attributes', () => {
  const html = render("[安全链接](https://example.com '\" onmouseover=\"alert(1)')");
  assert.match(html, /href="https:\/\/example\.com"/);
  assert.doesNotMatch(html, /onmouseover="/i);
  assert.match(html, /title="&quot; onmouseover=&quot;alert\(1\)"/);
});
