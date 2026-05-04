# api/index.py - 视频字幕提取 API（5.0版）
from flask import Flask, request, jsonify
import subprocess
import json
import os
import tempfile
import re
import sys

app = Flask(__name__)

# 允许跨域
@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def parse_srt(srt_text):
    result = []
    blocks = re.split(r'\n\n+', srt_text.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 2:
            time_idx = 1
            if '-->' not in lines[1] and len(lines) > 2:
                time_idx = 2
            if time_idx < len(lines) and '-->' in lines[time_idx]:
                time_part = lines[time_idx].split('-->')[0].strip()
                parts = time_part.replace(',', ':').split(':')
                try:
                    if len(parts) >= 3:
                        secs = int(parts[-3]) * 3600 + int(parts[-2]) * 60 + int(float(parts[-1]))
                    else:
                        secs = 0
                    text = ' '.join(lines[time_idx + 1:]).strip()
                    if text:
                        result.append({'start': format_time(secs), 'text': text})
                except:
                    text = ' '.join(lines[time_idx + 1:]).strip()
                    if text:
                        result.append({'start': '', 'text': text})
    return result

def parse_vtt(vtt_text):
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
                    if not l.startswith('NOTE') and not l.startswith('STYLE'):
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
def extract_subtitle():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        data = request.get_json(force=True)
        url = data.get('url', '').strip()

        if not url:
            return jsonify({'success': False, 'message': '缺少视频链接'}), 400

        print(f"[INFO] 收到提取请求: {url}", file=sys.stderr)

        with tempfile.TemporaryDirectory() as tmpdir:
            # 策略1：提取字幕
            extract_cmd = [
                'yt-dlp',
                '--skip-download',
                '--write-auto-sub',
                '--write-sub',
                '--sub-lang', 'all',
                '--sub-format', 'srt/vtt',
                '--convert-subs', 'srt',
                '--no-warnings',
                '--no-check-certificate',
                '--user-agent', 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36',
                '-o', f'{tmpdir}/video.%(ext)s',
                url
            ]
            
            print(f"[INFO] 策略1：尝试提取字幕", file=sys.stderr)
            
            result = subprocess.run(
                extract_cmd,
                capture_output=True,
                text=True,
                cwd=tmpdir,
                timeout=120
            )

            # 获取视频信息
            info_cmd = [
                'yt-dlp',
                '--dump-json',
                '--skip-download',
                '--no-warnings',
                '--no-check-certificate',
                url
            ]
            
            info_result = subprocess.run(info_cmd, capture_output=True, text=True, cwd=tmpdir, timeout=45)
            
            title = '未知标题'
            platform = '未知平台'
            
            if info_result.returncode == 0:
                try:
                    video_info = json.loads(info_result.stdout)
                    title = video_info.get('title', '未知标题')
                    platform = video_info.get('extractor', '未知平台')
                except:
                    pass
            
            # 读取字幕文件
            subtitles = []
            detected_lang = '自动检测'
            
            for fname in os.listdir(tmpdir):
                if fname.endswith('.srt') or fname.endswith('.vtt'):
                    print(f"[INFO] 找到字幕文件: {fname}", file=sys.stderr)
                    try:
                        with open(os.path.join(tmpdir, fname), 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        if fname.endswith('.srt'):
                            parsed = parse_srt(content)
                        else:
                            parsed = parse_vtt(content)
                        
                        if parsed:
                            subtitles = parsed
                            lang_match = re.search(r'\.([a-zA-Z]{2,}(?:-[a-zA-Z]{2,})?)\.(?:srt|vtt)', fname)
                            if lang_match:
                                detected_lang = lang_match.group(1)
                            print(f"[INFO] 解析成功，条数: {len(subtitles)}, 语言: {detected_lang}", file=sys.stderr)
                            break
                    except Exception as e:
                        print(f"[ERROR] 解析字幕失败: {e}", file=sys.stderr)
                        continue

            # 策略2：获取视频描述
            if not subtitles:
                print("[INFO] 未找到字幕，尝试获取视频描述", file=sys.stderr)
                try:
                    desc_cmd = ['yt-dlp', '--get-description', '--skip-download', '--no-warnings', url]
                    desc_result = subprocess.run(desc_cmd, capture_output=True, text=True, cwd=tmpdir, timeout=30)
                    if desc_result.returncode == 0 and desc_result.stdout.strip():
                        desc_text = desc_result.stdout.strip()
                        lines = [l for l in desc_text.split('\n') if l.strip()][:200]
                        if lines:
                            subtitles = [{'start': '', 'text': l} for l in lines]
                            detected_lang = '视频描述'
                except:
                    pass

            if not subtitles:
                error_msg = result.stderr[:300] if result.stderr else '视频可能没有字幕'
                return jsonify({
                    'success': False,
                    'message': f'无法提取字幕。原因：{error_msg}'
                }), 400

            return jsonify({
                'success': True,
                'title': title,
                'platform': platform,
                'language': detected_lang,
                'subtitles': subtitles[:500]
            })

    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '请求超时（>120秒）'}), 500
    except Exception as e:
        error_msg = str(e)[:300]
        print(f"[ERROR] 服务器错误: {error_msg}", file=sys.stderr)
        return jsonify({'success': False, 'message': f'服务器错误：{error_msg}'}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'video-subtitle-api', 'version': '5.0'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
