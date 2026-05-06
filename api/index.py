#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频字幕提取 API - 超简版（Vercel专用）
只提取YouTube等海外平台的字幕，确保部署成功
"""

from flask import Flask, request, jsonify
import subprocess
import json
import os
import tempfile
import re

app = Flask(__name__)

# CORS 支持
@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

def format_time(seconds):
    """格式化时间"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def parse_srt(srt_text):
    """解析SRT字幕"""
    result = []
    blocks = re.split(r'\n\n+', srt_text.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 2:
            for i, line in enumerate(lines):
                if '-->' in line:
                    time_part = line.split('-->')[0].strip()
                    parts = time_part.replace(',', ':').split(':')
                    try:
                        if len(parts) >= 3:
                            secs = int(parts[-3]) * 3600 + int(parts[-2]) * 60 + int(float(parts[-1]))
                        else:
                            secs = 0
                        text = ' '.join(lines[i+1:]).strip()
                        if text:
                            result.append({'start': format_time(secs), 'text': text})
                    except:
                        pass
                    break
    return result

def parse_vtt(vtt_text):
    """解析VTT字幕"""
    result = []
    lines = vtt_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if '-->' in line:
            time_part = line.split('-->')[0].strip()
            parts = time_part.replace('.', ':').replace(',', ':').split(':')
            try:
                if len(parts) >= 3:
                    secs = int(parts[-3]) * 3600 + int(parts[-2]) * 60 + int(float(parts[-1]))
                else:
                    secs = 0
                text_parts = []
                i += 1
                while i < len(lines) and lines[i].strip() and '-->' not in lines[i]:
                    l = lines[i].strip()
                    if not l.startswith('NOTE'):
                        text_parts.append(l)
                    i += 1
                if text_parts:
                    result.append({'start': format_time(secs), 'text': ' '.join(text_parts)})
                continue
            except:
                pass
        i += 1
    return result

@app.route('/api/extract', methods=['POST', 'OPTIONS'])
def extract():
    """提取字幕"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json(force=True)
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'success': False, 'message': '请输入视频链接'}), 400
        
        print(f"[INFO] 提取: {url}", file=sys.stderr)
        
        # 使用临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            # 下载字幕
            cmd = [
                'yt-dlp',
                '--skip-download',
                '--write-auto-sub',
                '--write-sub',
                '--sub-lang', 'zh-Hans,zh-Hant,zh,en,all',
                '--sub-format', 'srt',
                '--convert-subs', 'srt',
                '--no-warnings',
                '--no-check-certificate',
                '--user-agent', 'Mozilla/5.0',
                '-o', f'{tmpdir}/%(id)s.%(ext)s',
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=tmpdir, timeout=60)
            print(f"[INFO] 返回码: {result.returncode}", file=sys.stderr)
            
            # 获取视频信息
            info_cmd = ['yt-dlp', '--dump-single-json', '--skip-download', '--no-warnings', url]
            info_result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
            
            title = '未知标题'
            if info_result.returncode == 0:
                try:
                    info = json.loads(info_result.stdout)
                    title = info.get('title', '未知标题')
                except:
                    pass
            
            # 查找字幕文件
            subtitles = []
            for fname in os.listdir(tmpdir):
                if fname.endswith('.srt'):
                    print(f"[INFO] 找到: {fname}", file=sys.stderr)
                    with open(os.path.join(tmpdir, fname), 'r', encoding='utf-8') as f:
                        content = f.read()
                    subtitles = parse_srt(content)[:300]  # 限制条数
                    if subtitles:
                        break
            
            if not subtitles:
                return jsonify({
                    'success': False,
                    'message': '无法提取字幕。可能原因：1) 视频无字幕 2) 视频非公开 3) 链接不正确'
                }), 400
            
            return jsonify({
                'success': True,
                'title': title,
                'platform': 'auto',
                'language': 'auto',
                'subtitles': subtitles
            })
    
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '超时（60秒），请重试'}), 500
    except Exception as e:
        print(f"[ERROR] {str(e)}", file=sys.stderr)
        return jsonify({'success': False, 'message': f'错误: {str(e)[:100]}'}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '7.0'})

if __name__ == '__main__':
    app.run()
