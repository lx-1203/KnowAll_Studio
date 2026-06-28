/**
 * 文件上传/下载客户端 — 分片上传 + WebSocket 实时通知
 * 对应规范文档 3.5 节
 */
import api from '../api';

export interface FileInfo {
  file_id: string;
  filename: string;
  size: number;
  mime_type?: string;
  url: string;
  version: number;
  uploaded_by?: string;
  uploaded_by_name?: string;
  parent_id?: string | null;
  timestamp?: number;
}

export interface UploadProgress {
  chunk: number;
  total: number;
  progress: number; // 0-1
}

export interface UploadResult {
  file_id: string;
  filename: string;
  size: number;
  url: string;
  version: number;
}

type ProgressCallback = (progress: UploadProgress) => void;

export class FileSyncClient {
  private spaceId: string;
  private userId: string;
  private fileList: FileInfo[] = [];
  private onFileListChange?: (files: FileInfo[]) => void;

  constructor(spaceId: string, userId: string) {
    this.spaceId = spaceId;
    this.userId = userId;
  }

  // ========== 上传 ==========

  /** 分片上传文件，支持进度回调 */
  async uploadFile(
    file: File,
    parentId: string | null = null,
    onProgress?: ProgressCallback,
  ): Promise<UploadResult> {
    // ① 初始化上传
    const initResp = await fetch('/api/upload/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: file.name,
        file_size: file.size,
        mime_type: file.type || 'application/octet-stream',
        space_id: this.spaceId,
        parent_id: parentId,
      }),
    });
    if (!initResp.ok) throw new Error(`上传初始化失败: ${initResp.status}`);
    const { data: initData } = await initResp.json();
    const { upload_id, chunk_size, total_chunks } = initData;

    // ② 分片上传
    for (let i = 0; i < total_chunks; i++) {
      const start = i * chunk_size;
      const chunk = file.slice(start, start + chunk_size);
      const formData = new FormData();
      formData.append('file', chunk, `chunk_${i}`);

      const chunkResp = await fetch(`/api/upload/${upload_id}/chunk/${i}`, {
        method: 'PUT',
        body: formData,
      });
      if (!chunkResp.ok) throw new Error(`分片 ${i} 上传失败`);

      const chunkResult = await chunkResp.json();
      onProgress?.({
        chunk: i + 1,
        total: total_chunks,
        progress: chunkResult.data?.progress ?? ((i + 1) / total_chunks),
      });
    }

    // ③ 完成上传
    const completeResp = await fetch(`/api/upload/${upload_id}/complete`, {
      method: 'POST',
    });
    if (!completeResp.ok) throw new Error('合并文件失败');
    const { data: fileData } = await completeResp.json();

    const fileInfo: FileInfo = {
      file_id: fileData.file_id,
      filename: fileData.filename,
      size: fileData.size,
      url: fileData.url,
      version: fileData.version,
      uploaded_by: this.userId,
      timestamp: Date.now(),
    };

    this.fileList.push(fileInfo);
    this.onFileListChange?.(this.fileList);

    return fileData;
  }

  // ========== 下载 ==========

  /** 下载文件 */
  async downloadFile(fileId: string): Promise<void> {
    const resp = await fetch(`/api/download/${fileId}`);
    if (!resp.ok) throw new Error(`下载失败: ${resp.status}`);

    const blob = await resp.blob();
    const disposition = resp.headers.get('Content-Disposition');
    const filename = disposition?.match(/filename="?(.+?)"?$/)?.[1] || 'download';
    this.saveBlob(blob, filename);
  }

  /** 获取下载 URL（用于 a 标签直接下载） */
  getDownloadUrl(fileId: string): string {
    return `/api/download/${fileId}`;
  }

  // ========== WebSocket 事件处理 ==========

  /** 处理来自 WebSocket 的文件事件 */
  handleFileEvent(msg: { type: string; data: Record<string, any> }): void {
    switch (msg.type) {
      case 'file_uploaded': {
        const existing = this.fileList.find(f => f.file_id === msg.data.file_id);
        if (!existing) {
          this.fileList.push(msg.data as FileInfo);
          this.onFileListChange?.(this.fileList);
        }
        break;
      }
      case 'file_deleted':
        this.fileList = this.fileList.filter(f => f.file_id !== msg.data.file_id);
        this.onFileListChange?.(this.fileList);
        break;

      case 'file_updated': {
        const file = this.fileList.find(f => f.file_id === msg.data.file_id);
        if (file) {
          file.version = msg.data.new_version;
          file.size = msg.data.size;
          file.url = msg.data.url;
        }
        this.onFileListChange?.(this.fileList);
        break;
      }
    }
  }

  // ========== 列表管理 ==========

  getFileList(): FileInfo[] {
    return this.fileList;
  }

  setFileList(files: FileInfo[]): void {
    this.fileList = files;
    this.onFileListChange?.(files);
  }

  onListChange(callback: (files: FileInfo[]) => void): void {
    this.onFileListChange = callback;
  }

  // ========== 辅助 ==========

  private saveBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}
