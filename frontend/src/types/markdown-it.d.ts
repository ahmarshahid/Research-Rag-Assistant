declare module "markdown-it" {
  interface MarkdownItOptions {
    html?: boolean;
    xhtmlOut?: boolean;
    breaks?: boolean;
    langPrefix?: string;
    linkify?: boolean;
    typographer?: boolean;
    quotes?: string;
  }

  class MarkdownIt {
    constructor(options?: MarkdownItOptions);
    render(md: string, env?: unknown): string;
    renderInline(md: string, env?: unknown): string;
  }

  export default MarkdownIt;
}
