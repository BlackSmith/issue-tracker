import { auth, reconcileAuthFailure } from './api'
import type { Attachment } from './types'

export function uploadAttachment(
  target: { itemId?: string; projectId?: string },
  file: File,
  onProgress: (percent: number) => void,
  signal: AbortSignal,
): Promise<Attachment> {
  return new Promise((resolve, reject) => {
    if (file.size > 20 * 1024 * 1024) return reject(new Error('File exceeds the 20 MB limit'))
    if (signal.aborted) return reject(new Error('Upload canceled'))

    const data = new FormData()
    data.append('file', file)
    const xhr = new XMLHttpRequest()
    const abort = () => xhr.abort()
    xhr.open('POST', target.itemId
      ? `/api/v1/items/${target.itemId}/attachments?pending=true`
      : `/api/v1/projects/${target.projectId}/attachments`)
    xhr.setRequestHeader('X-CSRF-Token', auth.csrf)
    signal.addEventListener('abort', abort, { once: true })
    xhr.onloadend = () => signal.removeEventListener('abort', abort)
    xhr.upload.onprogress = event => {
      if (event.lengthComputable) onProgress(Math.round(event.loaded / event.total * 100))
    }
    xhr.onerror = () => reject(new Error('Upload failed. Check your connection.'))
    xhr.onabort = () => reject(new Error('Upload canceled'))
    xhr.onload = async () => {
      try {
        const result = JSON.parse(xhr.responseText)
        if (xhr.status >= 400) {
          const message = typeof result.detail === 'string' ? result.detail : 'Upload failed'
          await reconcileAuthFailure(xhr.status, message)
          reject(new Error(message))
        }
        else resolve(result)
      } catch { reject(new Error('Upload failed')) }
    }
    xhr.send(data)
  })
}
