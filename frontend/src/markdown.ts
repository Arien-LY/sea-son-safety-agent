import MarkdownIt from "markdown-it";

const SAFE_LINK_PROTOCOL = /^(https?:|mailto:)/i;

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: false,
  typographer: false,
});

markdown.validateLink = (url: string) => SAFE_LINK_PROTOCOL.test(url.trim());

markdown.renderer.rules.link_open = (tokens, index, options, _env, renderer) => {
  const token = tokens[index];
  token.attrSet("target", "_blank");
  token.attrSet("rel", "noopener noreferrer");
  return renderer.renderToken(tokens, index, options);
};

markdown.renderer.rules.image = (tokens, index, options, env, renderer) => {
  const token = tokens[index];
  const alt = renderer.renderInlineAsText(token.children ?? [], options, env).trim();
  return `<span class="markdown-image-alt">[图片${alt ? `：${markdown.utils.escapeHtml(alt)}` : ""}]</span>`;
};

for (const suffix of ["open", "close"] as const) {
  markdown.renderer.rules[`heading_${suffix}`] = (tokens, index, options, _env, renderer) => {
    const token = tokens[index];
    const level = Number(token.tag.slice(1));
    token.tag = `h${Math.min(6, level + 1)}`;
    return renderer.renderToken(tokens, index, options);
  };
}

export function renderAssistantMarkdown(source: string): string {
  return markdown.render(source);
}
