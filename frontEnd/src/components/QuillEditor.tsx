import { useEffect, useState } from "react";
import ReactQuill from "react-quill";
import "react-quill/dist/quill.snow.css"; // 引入默认样式
import TurndownService from "turndown";
import showdown from "showdown";
import "./QuillEditor.css"; // 自定义样式

interface QuillEditorProps {
  value?: string;
  onChange?: (content: string) => void;
  placeholder?: string;
  editable?: boolean;
  minHeight?: number;
}

// 创建 HTML 到 Markdown 的转换器
const turndownService = new TurndownService({
  headingStyle: "atx",
  codeBlockStyle: "fenced",
  emDelimiter: "*",
  bulletListMarker: "-",
  strongDelimiter: "**",
});

// 添加自定义规则以支持更多格式
// 添加类型定义以解决TypeScript错误
interface TurndownNode extends Node {
  style?: {
    color?: string;
    backgroundColor?: string;
  };
}

// 支持删除线
turndownService.addRule("strikethrough", {
  filter: ["del", "s"],
  replacement: function (content) {
    return "~~" + content + "~~";
  },
});

// 支持下划线（通过HTML标签，因为Markdown本身不支持）
turndownService.addRule("underline", {
  filter: ["u"],
  replacement: function (content) {
    return "<u>" + content + "</u>";
  },
});

// 支持颜色（通过HTML标签，因为Markdown本身不支持）
turndownService.addRule("color", {
  filter: function (node: TurndownNode): boolean {
    return !!node.style && !!(node.style.color || node.style.backgroundColor);
  },
  replacement: function (content: string, node: TurndownNode) {
    let style = "";
    if (node.style?.color) style += `color:${node.style.color};`;
    if (node.style?.backgroundColor)
      style += `background-color:${node.style.backgroundColor};`;
    return style ? `<span style="${style}">${content}</span>` : content;
  },
});

// 创建 Markdown 到 HTML 的转换器，使用 GitHub Flavored Markdown
const converter = new showdown.Converter({
  tables: true,
  tasklists: true,
  strikethrough: true,
  emoji: true,
  underline: true,
  ghCodeBlocks: true,
  ghMentions: true,
  ghMentionsLink: "https://github.com/{u}",
  openLinksInNewWindow: true,
  parseImgDimensions: true,
  simplifiedAutoLink: true,
});

export default function QuillEditor({
  value = "",
  onChange,
  placeholder = "开始输入...",
  editable = true,
  minHeight = 200,
}: QuillEditorProps) {
  // 内部使用 HTML 格式
  const [editorHtml, setEditorHtml] = useState("");

  // 当外部 value (Markdown) 改变时更新编辑器内容
  useEffect(() => {
    if (value) {
      try {
        // 将 Markdown 转换为 HTML
        const html = converter.makeHtml(value);
        setEditorHtml(html);
      } catch (error) {
        console.warn("Failed to convert markdown to HTML:", error);
        // 如果转换失败，直接使用原始值
        setEditorHtml(value);
      }
    } else {
      setEditorHtml("");
    }
  }, [value]);

  // 当编辑器内容改变时触发 onChange 回调
  const handleChange = (html: string) => {
    setEditorHtml(html);

    if (onChange) {
      try {
        // 将 HTML 转换为 Markdown
        const markdown = turndownService.turndown(html);
        onChange(markdown);
      } catch (error) {
        console.warn("Failed to convert HTML to markdown:", error);
        // 如果转换失败，直接使用 HTML
        onChange(html);
      }
    }
  };

  // Quill 编辑器的工具栏配置
  const modules = {
    // 只在可编辑模式下显示工具栏
    toolbar: editable
      ? [
          [{ header: [1, 2, 3, 4, 5, false] }],
          ["bold", "italic", "underline"],
          [{ color: [] }, { background: [] }],
          [{ align: [] }],
          [{ list: "ordered" }, { list: "bullet" }],
          ["link", "image", "blockquote"],
        ]
      : false,
  };

  // 格式化选项
  const formats = [
    "header",
    "bold",
    "italic",
    "underline",
    "color",
    "background",
    "align",
    "list",
    "bullet",
    "link",
    "image",
    "blockquote",
  ];

  return (
    <div className="quill-editor-container">
      <ReactQuill
        key={String(editable)}
        theme="snow"
        value={editorHtml}
        onChange={handleChange}
        modules={modules}
        formats={formats}
        placeholder={placeholder}
        readOnly={!editable}
        style={{ minHeight: `${minHeight}px` }}
      />
    </div>
  );
}
