import { FileTreeNode } from "./data";

// 递归添加Path属性的辅助函数
export const addPathToFileTreeNodes = (
  nodes: FileTreeNode[],
  parentPath: string = ""
): (FileTreeNode & { Path: string })[] => {
  return nodes.map((node) => {
    const currentPath = parentPath
      ? `${parentPath}/${node.Name}`
      : `/${node.Name}`;
    const nodeWithPath = {
      ...node,
      Path: currentPath,
    };

    if (node.Children && node.Children.length > 0) {
      nodeWithPath.Children = addPathToFileTreeNodes(
        node.Children,
        currentPath
      );
    }

    return nodeWithPath;
  });
};
