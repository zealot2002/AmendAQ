import type { TocNode } from "@/api/client";

export interface TreeNode extends TocNode {
  children: TreeNode[];
}

export function buildTocTree(nodes: TocNode[]): TreeNode[] {
  const map = new Map<string, TreeNode>();
  for (const n of nodes) {
    map.set(n.node_id, { ...n, children: [] });
  }
  const roots: TreeNode[] = [];
  for (const n of nodes) {
    const item = map.get(n.node_id)!;
    if (n.parent_id && map.has(n.parent_id)) {
      map.get(n.parent_id)!.children.push(item);
    } else {
      roots.push(item);
    }
  }
  return roots;
}
