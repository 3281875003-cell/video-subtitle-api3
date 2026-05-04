// pages/result/result.js
Page({
  data: {
    title: '',
    platform: '',
    language: '',
    subtitles: [],
    showAll: false
  },

  onLoad() {
    try {
      const result = wx.getStorageSync('subtitleResult')
      if (result && result.success) {
        this.setData({
          title: result.title || '未知标题',
          platform: result.platform || '未知平台',
          language: result.language || '未知',
          subtitles: result.subtitles || []
        })
      } else {
        wx.showToast({ title: '未找到数据', icon: 'none' })
        setTimeout(() => wx.navigateBack(), 1500)
      }
    } catch (e) {
      wx.showToast({ title: '数据读取失败', icon: 'none' })
    }
  },

  onShowAll() {
    this.setData({ showAll: !this.data.showAll })
  },

  onCopyAll() {
    const text = this.data.subtitles.map(item => {
      if (item.start) {
        return '[' + item.start + '] ' + item.text
      }
      return item.text
    }).join('\n')

    wx.setClipboardData({
      data: text,
      success: () => {
        wx.showToast({ title: '已复制全部字幕', icon: 'success' })
      }
    })
  },

  onCopyTextOnly() {
    const text = this.data.subtitles.map(item => item.text).join('\n')

    wx.setClipboardData({
      data: text,
      success: () => {
        wx.showToast({ title: '已复制纯文本', icon: 'success' })
      }
    })
  },

  onBack() {
    wx.navigateBack()
  },

  onShareAppMessage() {
    return {
      title: '视频字幕提取工具 - 免费提取视频文案',
      path: '/pages/index/index'
    }
  }
})
