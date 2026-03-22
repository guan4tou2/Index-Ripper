export interface TreeNode {
  id: string
  parentId: string          // "" for roots
  name: string
  kind: 'folder' | 'file'
  url: string               // download URL (files only, "" for folders)
  fullPath: string          // relative path
  size: string              // "245 KB" or "Unknown"
  fileType: string          // MIME type
  iconGroup: string         // folder|image|document|archive|code|audio|video|text|binary
  checked: boolean
  expanded: boolean
  hidden: boolean           // filtered out by search/type
  children: string[]        // child node IDs
}

export interface Task {
  id: string
  url: string
  status: 'idle' | 'scanning' | 'scanned' | 'downloading' | 'done' | 'error' | 'cancelled'
  nodes: Record<string, TreeNode>
  roots: string[]
  checkedFiles: string[]
  downloads: Record<string, DownloadItem>
  scanProgress: { scanned: number; total: number }
  downloadPath: string
}

export interface DownloadItem {
  id: string
  fileName: string
  url: string
  destPath: string
  status: 'queued' | 'downloading' | 'paused' | 'completed' | 'failed' | 'cancelled'
  progress: number
  speed: number
  totalSize: number
  downloadedSize: number
}

export type ScanStatus = Task['status']
export type DownloadStatus = DownloadItem['status']
