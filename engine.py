"""Local browser based Douyin downloader. No third-party parsing service."""
import os
import re
import time
import json
import queue
import threading
import subprocess
from pathlib import Path
from urllib.parse import urlparse, parse_qs

DEFAULT_URL = 'https://v.douyin.com/DE4UEeJ2lXY/'

def clean_url(text):
    match = re.search(r'https?://[^\s<>"\u3000]+', text.replace('\\:', ':'))
    if not match:
        raise ValueError('Hãy dán link trang cá nhân hoặc video Douyin.')
    url = match.group(0).rstrip('.,;，。)）')
    host = (urlparse(url).hostname or '').lower()
    if host != 'douyin.com' and not host.endswith('.douyin.com'):
        raise ValueError('Chỉ nhận link douyin.com hoặc v.douyin.com.')
    if urlparse(url).username or urlparse(url).password:
        raise ValueError('Link không hợp lệ.')
    return url

def safe_name(text):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(text))
    text = text.strip(' .')[:95].rstrip(' .')
    if text.upper().split('.')[0] in {'CON','PRN','AUX','NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}:
        text = '_' + text
    return text or 'video'

def parse_aweme(item):
    vid = str(item.get('aweme_id', ''))
    if not vid.isdigit():
        return None
    video = item.get('video') or {}
    candidates = []
    for stream in video.get('bit_rate') or []:
        addr = stream.get('play_addr') or {}
        candidates.extend((int(stream.get('bit_rate') or 0), u) for u in addr.get('url_list', []) if u.startswith('https://'))
    for key in ('play_addr', 'play_addr_h264', 'download_addr'):
        candidates.extend((0, u) for u in (video.get(key) or {}).get('url_list', []) if u.startswith('https://'))
    candidates.sort(reverse=True)
    urls = list(dict.fromkeys(u for _,u in candidates))
    author = item.get('author') or {}
    statistics = item.get('statistics') or {}
    views = statistics.get('play_count')
    # Public Douyin responses may use zero as a placeholder for hidden views.
    views = int(views) if str(views).isdigit() and int(views)>0 else None
    likes = statistics.get('digg_count')
    likes = int(likes) if str(likes).isdigit() else None
    return {'id':vid, 'title':item.get('desc') or f'Video {vid}',
            'views':views, 'likes':likes,
            'duration':round(float(video.get('duration') or item.get('duration') or 0)/1000,1),
            'created':int(item.get('create_time') or 0), 'urls':urls,
            'author':author.get('nickname',''), 'sec_uid':author.get('sec_uid',''),
            'is_image':bool(item.get('images')),
            'url':f'https://www.douyin.com/video/{vid}'}

def filter_records(records,metric,threshold,mode):
    if threshold<0: raise ValueError('Mức lọc phải từ 0 trở lên.')
    known={vid:r[metric] for vid,r in records.items() if isinstance(r.get(metric),int) and (metric!='views' or r[metric]>0)}
    if not known:
        raise ValueError('Không có dữ liệu cho tiêu chí này. Giữ nguyên các video đang chọn.')
    selected={vid for vid,value in known.items() if (value>=threshold if mode=='Từ mức này trở lên' else value<threshold)}
    return selected,len(records)-len(known)

class Cancelled(Exception): pass

class Engine:
    def __init__(self, emit, profile_dir):
        self.emit = emit
        self.profile_dir = Path(profile_dir)
        self.jobs = queue.Queue()
        self.stop = threading.Event()
        self.records = {}
        self.context = None
        self.page = None
        self.collect = False
        self.target_sec = ''
        self.detail_id = ''
        self.limit = 30
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def submit(self, action, *args):
        self.stop.clear()
        self.jobs.put((action,args))

    def run(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as self.pw:
            while True:
                try:
                    action,args = self.jobs.get(timeout=.2)
                except queue.Empty:
                    if self.context:
                        try: self.context.pages[0].wait_for_timeout(100)
                        except Exception: self.context = None
                    continue
                if action == 'quit':
                    if self.context:
                        try: self.context.close()
                        except Exception: pass
                    return
                try:
                    getattr(self,action)(*args)
                except Cancelled:
                    self.emit('status','Đã dừng. Các video tải xong vẫn được giữ lại.')
                except Exception as exc:
                    self.emit('error', str(exc)[:650])
                finally:
                    self.collect = False
                    self.detail_id = ''
                    self.emit('idle',None)

    def check(self):
        if self.stop.is_set(): raise Cancelled()

    def ensure_browser(self):
        if self.context:
            try:
                self.page.title()
                return
            except Exception: self.context = None
        self.profile_dir.mkdir(parents=True,exist_ok=True)
        try:
            self.context = self.pw.chromium.launch_persistent_context(
                str(self.profile_dir), channel='msedge', headless=False,
                viewport=None, locale='zh-CN', accept_downloads=False,
                timeout=30000, args=['--start-maximized'])
        except Exception as exc:
            raise RuntimeError('Không mở được cửa sổ Edge dành riêng cho app. Hãy kiểm tra Microsoft Edge đã cài, đóng cửa sổ Edge của app nếu còn mở rồi thử lại. Chi tiết: '+str(exc).split('Browser logs:')[0][:200]) from exc
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.context.on('response',self.on_response)

    def on_response(self,response):
        try:
            path = urlparse(response.url).path
            if '/aweme/v1/web/aweme/post/' in path and self.collect:
                # Only the requested profile; never ingest recommendation feeds.
                sec = parse_qs(urlparse(response.url).query).get('sec_user_id',[''])[0]
                if self.target_sec and sec != self.target_sec: return
                data = response.json()
                for item in data.get('aweme_list') or []: self.add(item)
                self.has_more = data.get('has_more',1)
            elif '/aweme/detail/' in path and self.detail_id:
                item = response.json().get('aweme_detail') or {}
                if str(item.get('aweme_id')) == self.detail_id: self.add(item, detail=True)
        except Exception:
            pass

    def add(self,item,detail=False):
        record = parse_aweme(item)
        if not record or record['is_image']: return
        if self.target_sec and not detail and record['sec_uid'] != self.target_sec: return
        old = self.records.get(record['id'])
        if not old and not detail and len(self.records) >= self.limit: return
        if old and old.get('urls') and not record['urls']: return
        self.records[record['id']] = record
        self.emit('record',record)

    def open_browser(self,url):
        self.ensure_browser()
        self.page.goto(clean_url(url),wait_until='domcontentloaded',timeout=60000)
        self.emit('status','Trình duyệt đã mở. Nếu cần, anh tự đăng nhập hoặc xác minh rồi quay lại bấm Quét.')

    def scan(self,url,limit):
        self.ensure_browser()
        self.records = {}
        self.limit = limit
        self.target_sec = ''
        self.has_more = 1
        self.collect = True
        parsed = urlparse(clean_url(url))
        if '/user/' in parsed.path:
            self.target_sec = parsed.path.split('/user/',1)[1].split('/')[0]
        match = re.search(r'/(?:video|note)/(\d+)',parsed.path)
        self.detail_id = match.group(1) if match else ''
        self.emit('status','Đang mở Douyin… Nếu có yêu cầu đăng nhập/xác minh, anh thao tác trong cửa sổ Edge vừa mở.')
        self.page.goto(clean_url(url),wait_until='domcontentloaded',timeout=60000)
        started=time.monotonic()
        last_change=started
        previous=0
        while time.monotonic()-started < 180:
            self.check()
            current=urlparse(self.page.url)
            if '/user/' in current.path:
                self.target_sec=current.path.split('/user/',1)[1].split('/')[0]
            match=re.search(r'/(?:video|note)/(\d+)',current.path)
            if match: self.detail_id=match.group(1)
            # Hydration payload sometimes contains the first page before an XHR.
            if self.target_sec or self.detail_id:
                scripts=self.page.locator('script[type="application/json"], script#RENDER_DATA').all_text_contents()
                from urllib.parse import unquote
                for raw in scripts:
                    try: self.read_hydration(json.loads(unquote(raw)))
                    except (ValueError,TypeError): pass
            if self.detail_id:
                self.capture_visible_video(self.detail_id)
            elif self.target_sec:
                # Only actual profile cards: the site's footer also links unrelated videos.
                nickname=self.page.title().split('的抖音')[0].replace(' ','').strip()
                links=self.page.locator('a[href*="/video/"]').evaluate_all('''(els,nickname)=>els.filter(a=>{
                    const alt=a.querySelector('img[alt]')?.alt||'';
                    return nickname && alt.replace(/\\s/g,'').startsWith(nickname+'：');
                }).map(a=>({href:a.href,title:a.querySelector('img[alt]').alt}))''',nickname)
                for link in links:
                    m=re.search(r'/video/(\d+)',link['href'])
                    if m and m.group(1) not in self.records:
                        rec={'id':m.group(1),'title':link['title'].strip() or f'Video {m.group(1)}','url':f'https://www.douyin.com/video/{m.group(1)}','urls':[],'views':None,'likes':None,'duration':0,'created':0,'author':'','sec_uid':self.target_sec,'is_image':False}
                        self.records[rec['id']]=rec
                        self.emit('record',rec)
                        if len(self.records)>=limit: break
            if len(self.records)!=previous:
                previous=len(self.records); last_change=time.monotonic()
                self.emit('status',f'Đã tìm thấy {previous} video. Đang đọc tiếp…')
            if len(self.records)>=limit or (self.detail_id and self.records): break
            if self.records and (time.monotonic()-last_change>18 or self.has_more==0): break
            if not self.records and time.monotonic()-started>12:
                self.emit('status','Chưa đọc được danh sách. Anh kiểm tra cửa sổ Edge: đăng nhập/xác minh nếu được yêu cầu. App đang chờ, có thể bấm Dừng.')
            dimensions=self.page.evaluate('({w:innerWidth,h:innerHeight})')
            self.page.mouse.move(dimensions['w']*.65,dimensions['h']*.7)
            self.page.mouse.wheel(0,1000)
            self.page.wait_for_timeout(1800)
        if not self.records:
            raise RuntimeError('Douyin chưa trả danh sách video. Hãy kiểm tra trình duyệt, tự đăng nhập/xác minh nếu cần, rồi Quét lại. Không cần gửi mật khẩu hay cookie cho ai.')
        self.emit('status',f'Quét xong: {min(len(self.records),limit)} video. Chọn video rồi bấm Tải video đã chọn.')

    def read_hydration(self,obj,depth=0):
        if depth>18: return
        if isinstance(obj,dict):
            if obj.get('aweme_id') and obj.get('video'):
                if self.detail_id and str(obj['aweme_id']) != self.detail_id: return
                self.add(obj,detail=bool(self.detail_id))
            else:
                for value in obj.values(): self.read_hydration(value,depth+1)
        elif isinstance(obj,list):
            for value in obj: self.read_hydration(value,depth+1)

    def capture_visible_video(self,vid):
        old=self.records.get(vid)
        if old and old['urls']: return
        src=self.page.locator('video').evaluate_all('(els)=>els.map(v=>v.currentSrc||v.src).filter(u=>u.startsWith("https://"))')
        if src:
            rec={'id':vid,'title':self.page.title().removesuffix(' - 抖音'),'views':0,'duration':0,'created':0,'urls':src,'url':f'https://www.douyin.com/video/{vid}','author':'','sec_uid':'','is_image':False}
            self.records[vid]=rec; self.emit('record',rec)

    def resolve(self,record):
        self.detail_id=record['id']
        self.page.goto(record['url'],wait_until='domcontentloaded',timeout=60000)
        for _ in range(15):
            self.check()
            self.page.wait_for_timeout(1000)
            self.capture_visible_video(record['id'])
            updated=self.records.get(record['id'],record)
            if updated.get('urls'): return updated
        raise RuntimeError('Chưa lấy được nguồn video. Kiểm tra trang trong Edge, đăng nhập/xác minh nếu có rồi thử lại.')

    def download(self,records,folder):
        import requests
        import imageio_ffmpeg
        self.ensure_browser()
        target=Path(folder).expanduser().resolve()
        target.mkdir(parents=True,exist_ok=True)
        session=requests.Session()
        session.headers.update({'User-Agent':self.page.evaluate('navigator.userAgent'),'Referer':'https://www.douyin.com/'})
        for c in self.context.cookies():
            session.cookies.set(c['name'],c['value'],domain=c['domain'],path=c['path'],secure=c['secure'])
        done=failed=skipped=0
        try:
            for idx,record in enumerate(records,1):
                self.check()
                vid=record['id']
                dest=target/f'{vid}_{safe_name(record["title"])}.mp4'
                pending=dest.with_suffix('.mp4.pending')
                self.emit('item',(vid,'Đang tải…'))
                try:
                    if dest.exists():
                        self.verify(dest,imageio_ffmpeg.get_ffmpeg_exe())
                        skipped+=1; self.emit('item',(vid,'Đã có • bỏ qua')); continue
                    if not record.get('urls'): record=self.resolve(record)
                    error=None
                    # Source links expire. Refresh once using the actual video page.
                    for attempt in range(2):
                        for url in record.get('urls',[]):
                            self.check()
                            try:
                                try:
                                    with session.get(url,stream=True,timeout=(15,20)) as response:
                                        response.raise_for_status()
                                        if 'text/' in response.headers.get('Content-Type',''): raise RuntimeError('Nguồn trả về trang web thay vì video.')
                                        size=int(response.headers.get('Content-Length') or 0)
                                        received=0
                                        with pending.open('wb') as out:
                                            for chunk in response.iter_content(256*1024):
                                                self.check()
                                                if not chunk: continue
                                                out.write(chunk); received+=len(chunk)
                                                self.emit('progress',(idx,len(records),received,size))
                                        if size and received!=size: raise RuntimeError('Tệp chưa tải đủ.')
                                except requests.RequestException:
                                    # Some Windows environments cannot open Requests' TLS
                                    # resources. Reuse the authenticated browser network stack.
                                    self.check()
                                    self.emit('item',(vid,'Đang tải qua trình duyệt…'))
                                    response=self.context.request.get(url,headers={'Referer':'https://www.douyin.com/','User-Agent':session.headers['User-Agent']},timeout=60000)
                                    try:
                                        if not response.ok: raise RuntimeError(f'Nguồn video trả HTTP {response.status}.')
                                        self.check()
                                        body=response.body()
                                        self.check()
                                        pending.write_bytes(body)
                                        self.emit('progress',(idx,len(records),len(body),len(body)))
                                    finally: response.dispose()
                                self.verify(pending,imageio_ffmpeg.get_ffmpeg_exe())
                                pending.replace(dest)
                                error=None
                                break
                            except Cancelled: raise
                            except Exception as exc: error=exc
                        if dest.exists(): break
                        if attempt==0:
                            self.records.pop(vid,None)
                            record=self.resolve(record)
                    if error or not dest.exists(): raise RuntimeError(str(error or 'Không có nguồn video khả dụng.'))
                    done+=1; self.emit('item',(vid,'Đã tải ✓'))
                except Cancelled:
                    self.emit('item',(vid,'Đã dừng')); raise
                except Exception as exc:
                    failed+=1; self.emit('item',(vid,'Lỗi: '+str(exc)[:160]))
                finally:
                    if pending.exists(): pending.unlink(missing_ok=True)
                    self.emit('progress',(idx,len(records),0,0))
            self.emit('status',f'Hoàn tất: {done} tải thành công · {skipped} đã có · {failed} lỗi. Thư mục: {target}')
        finally:
            session.close()

    @staticmethod
    def verify(path,ffmpeg):
        if path.stat().st_size < 1024: raise RuntimeError('Tệp video quá nhỏ hoặc rỗng.')
        with path.open('rb') as f:
            if b'ftyp' not in f.read(64): raise RuntimeError('Nguồn trả về không phải video MP4.')
        result=subprocess.run([ffmpeg,'-v','error','-xerror','-i',str(path),'-t','1','-map','0:v:0','-map','0:a?','-f','null','-'],capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode: raise RuntimeError('Video không giải mã được; chưa đánh dấu tải thành công.')
