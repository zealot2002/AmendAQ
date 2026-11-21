import raw from "../../../config/prompts.txt?raw";

function promptSection(name: string, source: string): string {
  const marker = `[${name}]\n`;
  const start = source.indexOf(marker);
  if (start < 0) {
    throw new Error(`missing prompt section ${name}`);
  }
  const rest = source.slice(start + marker.length);
  const next = rest.search(/^\[([a-z0-9_]+)\]\s*$/m);
  const body = next < 0 ? rest : rest.slice(0, next);
  return body.replace(/\s+$/, "");
}

/** 与 config/prompts.txt 的 [organize_external] 同一份。 */
export const EXTERNAL_ORGANIZE_PROMPT = promptSection("organize_external", raw);

export const EXTERNAL_ORGANIZE_HINT =
  "杂乱 Word / 表格请先用豆包等按下方 Prompt 整理为 .md，再上传。入库不符合规范会直接失败。";
