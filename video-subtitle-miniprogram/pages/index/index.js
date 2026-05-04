// pages/index/index.js
const app = getApp()

Page({
  data: {
    videoUrl: '',
    loading: false,
    loadingText: '正在解析视频链接...'
  },

  onUrlInput(e) {
    let url = e.detail.value
    url = this.cleanVideoUrl(url)
    this.setData({ videoUrl: url })
  },

  onPaste() {
    wx.getClipboardData({
      success: (res) => {
        if (res.data) {
          let url = this.cleanVideoUrl(res.data)
          this.setData({ videoUrl: url })
        } else {
          wx.showToast({ title: '剪贴板为空', icon: 'none' })
        }
      }
    })
  },

  // 智能清洗视频链接
  cleanVideoUrl(text) {
    if (!text) return ''
    text = text.trim()
    
    // 0. 特殊处理：抖音/TikTok 分享文本
    const douyinPatterns = [
      /https?:\/\/v\.douyin\.com\/[A-Za-z0-9_\-]+\/?/,
      /https?:\/\/www\.douyin\.com\/video\/[0-9]+/,
      /https?:\/\/m\.douyin\.com\/[A-Za-z0-9\/\-_]+/,
      /https?:\/\/www\.tiktok\.com\/@[^\/]+\/video\/[0-9]+/,
      /https?:\/\/vm\.tiktok\.com\/[A-Za-z0-9_\-]+/
    ]
    
    for (let pattern of douyinPatterns) {
      const match = text.match(pattern)
      if (match) {
        return match[0].split('?')[0]
      }
    }
    
    // 1. 尝试从分享文本中提取URL
    const urlRegex = /(https?:\/\/[^\s\u4e00-\u9fa5]+)/i
    const match = text.match(urlRegex)
    if (match) {
      let url = match[1]
      
      try {
        const urlObj = new URL(url)
        
        // 2. 清理YouTube链接
        if (urlObj.hostname.includes('youtube') || urlObj.hostname.includes('youtu.be')) {
          let videoId = ''
          if (urlObj.hostname.includes('youtu.be')) {
            videoId = urlObj.pathname.split('/')[1]
          } else {
            videoId = urlObj.searchParams.get('v')
          }
          if (videoId) {
            return `https://www.youtube.com/watch?v=${videoId}`
          }
        }
        
        // 3. 清理B站链接
        if (urlObj.hostname.includes('bilibili')) {
          const bvid = urlObj.searchParams.get('bvid') || urlObj.pathname.match(/\/video\/([^\/\?]+)/)?.[1]
          if (bvid) {
            return `https://www.bilibili.com/video/${bvid}`
          }
        }
        
        // 4. 清理抖音/TikTok链接
        if (urlObj.hostname.includes('douyin') || 
            urlObj.hostname.includes('tiktok')) {
          return url.split('?')[0].replace(/\/+$/, '')
        }
        
        // 5. 通用清理
        const keepParams = ['v', 'bvid', 'video_id', 'id', 'vid']
        const hasKeepParam = keepParams.some(p => urlObj.searchParams.has(p))
        
        if (hasKeepParam) {
          const params = new URLSearchParams()
          keepParams.forEach(p => {
            if (urlObj.searchParams.has(p)) {
              params.append(p, urlObj.searchParams.get(p))
            }
          })
          return `${urlObj.origin}${urlObj.pathname}?${params.toString()}`
        }
        
        return `${urlObj.origin}${urlObj.pathname}`.replace(/\/+$/, '')
        
      } catch (e) {
        return text
      }
    }
    
    return text
  },

  onExtract() {
    const { videoUrl } = this.data

    if (!videoUrl || !videoUrl.trim()) {
      wx.showToast({ title: '请先粘贴视频链接', icon: 'none' })
      return
    }

    if (!/^https?:\/\//i.test(videoUrl.trim())) {
      wx.showToast({ title: '链接格式不正确', icon: 'none' })
      return
    }

    this.setData({ loading: true, loadingText: '正在解析视频链接...' })

    wx.request({
      url: `${app.globalData.apiBaseUrl}/api/extract`,
      method: 'POST',
      header: { 'content-type': 'application/json' },
      data: {
        url: videoUrl.trim()
      },
      success: (res) => {
        this.setData({ loading: false })
        if (res.statusCode === 200 && res.data.success) {
          wx.setStorageSync('subtitleResult', res.data)
          wx.navigateTo({ url: '/pages/result/result' })
        } else {
          wx.showModal({
            title: '提取失败',
            content: res.data.message || '无法提取该视频字幕，请确认视频为公开且含有字幕',
            showCancel: false
          })
        }
      },
      fail: (err) => {
        this.setData({ loading: false })
        wx.showModal({
          title: '网络错误',
          content: '无法连接服务器，请检查网络或稍后重试',
          showCancel: false
        })
      }
    })
  }
})