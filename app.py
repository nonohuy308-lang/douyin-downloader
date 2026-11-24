import os
import sys
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from engine import Engine, DEFAULT_URL, clean_url, filter_records

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Douyin • Tải video theo lựa chọn • 1.1')
        self.geometry('1180x800')
        self.minsize(980,680)
        self.configure(bg='#f8f7f3')
        self.events=queue.Queue()
        self.records={}; self.selected=set(); self.busy=False; self.limit=30
        self.url=tk.StringVar(value=DEFAULT_URL)
        self.count=tk.IntVar(value=30)
        self.folder=tk.StringVar(value=str(Path.home()/'Downloads'/'Douyin-Videos'))
        self.status=tk.StringVar(value='Sẵn sàng. Dán link kênh Douyin rồi bấm Quét kênh / video.')
        self.total=tk.StringVar(value='Chưa có video')
        self.filter=tk.StringVar(value='Không lọc')
        self.metric=tk.StringVar(value='Lượt thích')
        self.threshold=tk.StringVar(value='1000')
        style=ttk.Style(self); style.theme_use('clam')
        style.configure('.',font=('Segoe UI',10),background='#f8f7f3')
        style.configure('TButton',padding=(14,9))
        style.configure('Accent.TButton',background='#007ea8',foreground='white')
        style.map('Accent.TButton',background=[('active','#006581')])
        style.configure('Treeview',rowheight=32,background='white',fieldbackground='white')
        style.configure('Treeview.Heading',font=('Segoe UI',10,'bold'),padding=8)
        outer=ttk.Frame(self,padding=20); outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='Tải video Douyin',font=('Segoe UI',27,'bold'),foreground='#06445d').pack(anchor='w')
        ttk.Label(outer,text='Dán link kênh → Quét danh sách → Chọn video → Tải về máy',foreground='#6c7983').pack(anchor='w',pady=(2,14))
        ttk.Label(outer,text='Link trang cá nhân hoặc video Douyin (nhận cả link v.douyin.com)').pack(anchor='w')
        ttk.Entry(outer,textvariable=self.url,font=('Segoe UI',11)).pack(fill='x',pady=(5,10),ipady=5)
        toolbar=ttk.Frame(outer); toolbar.pack(fill='x')
        ttk.Label(toolbar,text='Số video quét').pack(side='left')
        ttk.Spinbox(toolbar,from_=1,to=1000,textvariable=self.count,width=6).pack(side='left',padx=(8,22))
        ttk.Label(toolbar,text='Chất lượng: tốt nhất từ nguồn',foreground='#6c7983').pack(side='left')
        self.scan_btn=ttk.Button(toolbar,text='Quét kênh / video',style='Accent.TButton',command=self.scan)
        self.scan_btn.pack(side='right')
        self.browser_btn=ttk.Button(toolbar,text='Mở Douyin / Đăng nhập',command=self.open_browser)
        self.browser_btn.pack(side='right',padx=8)
        ttk.Label(outer,text='Nếu Douyin yêu cầu đăng nhập hoặc xác minh, anh tự thực hiện trong cửa sổ Edge của app rồi quét lại.',foreground='#6c7983',wraplength=1100).pack(anchor='w',pady=(9,14))
        selection=ttk.Frame(outer); selection.pack(fill='x')
        ttk.Button(selection,text='Chọn tất cả',command=lambda:self.select_all(True)).pack(side='left')
        ttk.Button(selection,text='Bỏ chọn',command=lambda:self.select_all(False)).pack(side='left',padx=7)
        ttk.Label(selection,textvariable=self.total).pack(side='right')
        filters=ttk.Frame(outer); filters.pack(fill='x',pady=10)
        ttk.Label(filters,text='Lọc theo').pack(side='left')
        ttk.Combobox(filters,textvariable=self.metric,values=['Lượt thích','Lượt xem'],state='readonly',width=12).pack(side='left',padx=(7,0))
        ttk.Combobox(filters,textvariable=self.filter,values=['Không lọc','Từ mức này trở lên','Dưới mức này'],state='readonly',width=22).pack(side='left',padx=7)
        ttk.Entry(filters,textvariable=self.threshold,width=12).pack(side='left')
        ttk.Button(filters,text='Lọc & chọn',command=self.filter_select).pack(side='left',padx=7)
        ttk.Label(filters,text='“—” = chưa có số liệu',foreground='#6c7983').pack(side='right')
        footer=ttk.Frame(outer); footer.pack(side='bottom',fill='x')
        table=ttk.Frame(outer); table.pack(fill='both',expand=True)
        self.table=ttk.Treeview(table,columns=('check','title','likes','views','duration','status'),show='headings',selectmode='extended',height=5)
        for name,title,width in [('check','Chọn',55),('title','Video',440),('likes','Lượt thích',100),('views','Lượt xem',100),('duration','Giây',65),('status','Trạng thái',245)]:
            self.table.heading(name,text=title); self.table.column(name,width=width,minwidth=45,stretch=name in ('title','status'))
        bar=ttk.Scrollbar(table,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=bar.set)
        bar.pack(side='right',fill='y'); self.table.pack(fill='both',expand=True)
        self.table.bind('<ButtonRelease-1>',self.toggle)
        self.table.bind('<space>',self.toggle_keyboard)
        save=ttk.Frame(footer); save.pack(fill='x',pady=(15,10))
        ttk.Label(save,text='Lưu vào').pack(side='left')
        ttk.Entry(save,textvariable=self.folder).pack(side='left',fill='x',expand=True,padx=8,ipady=5)
        ttk.Button(save,text='Chọn thư mục',command=self.choose_folder).pack(side='left')
        ttk.Button(save,text='Mở',command=self.open_folder).pack(side='left',padx=(7,0))
        actions=ttk.Frame(footer); actions.pack(fill='x')
        self.download_btn=ttk.Button(actions,text='↓ Tải video đã chọn',style='Accent.TButton',command=self.download)
        self.download_btn.pack(side='left')
        self.stop_btn=ttk.Button(actions,text='Dừng',command=self.cancel,state='disabled'); self.stop_btn.pack(side='left',padx=8)
        self.progress=ttk.Progressbar(actions,maximum=100); self.progress.pack(side='left',fill='x',expand=True,padx=(18,0))
        ttk.Label(footer,textvariable=self.status,wraplength=1100).pack(anchor='w',pady=(12,4))
        ttk.Label(footer,text='Tải video công khai mà anh có quyền sử dụng. Chưa hỗ trợ bài ảnh, kênh riêng tư hoặc vượt xác minh.',foreground='#7d858b',wraplength=1100).pack(anchor='w')
        base=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'DouyinDownloader'
        self.engine=Engine(lambda a,b:self.events.put((a,b)),base/'BrowserProfile')
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.after(100,self.poll)

    def set_busy(self,value):
        self.busy=value
        for btn in (self.scan_btn,self.browser_btn,self.download_btn): btn.configure(state='disabled' if value else 'normal')
        self.stop_btn.configure(state='normal' if value else 'disabled')

    def get_url(self):
        try: return clean_url(self.url.get())
        except ValueError as e: messagebox.showwarning('Link Douyin',str(e)); return None

    def scan(self):
        url=self.get_url()
        if not url or self.busy: return
        try:
            self.limit=int(self.count.get())
            if not 1<=self.limit<=1000: raise ValueError()
        except (ValueError,tk.TclError):
            messagebox.showwarning('Số video','Chọn từ 1 đến 1000 video.'); return
        self.table.delete(*self.table.get_children()); self.records.clear(); self.selected.clear(); self.update_total()
        self.progress['value']=0
        self.set_busy(True); self.engine.submit('scan',url,self.limit)

    def open_browser(self):
        url=self.get_url()
        if url and not self.busy:
            self.set_busy(True); self.engine.submit('open_browser',url)

    def update_total(self):
        self.total.set(f'{len(self.records)} video · {len(self.selected)} đã chọn')

    def row(self,rec,status=None):
        vid=rec['id']
        if vid not in self.records and len(self.records)>=self.limit: return
        self.records[vid]=rec
        if self.table.exists(vid):
            previous=self.table.item(vid,'values')[-1]
        else: previous='Sẵn sàng'
        likes=rec.get('likes')
        values=('☑' if vid in self.selected else '☐',rec['title'].replace('\n',' '),f'{likes:,}' if likes is not None else '—',f'{rec["views"]:,}' if rec.get('views') else '—',rec['duration'] or '—',status or previous)
        if self.table.exists(vid): self.table.item(vid,values=values)
        else: self.table.insert('', 'end',iid=vid,values=values)
        self.update_total()

    def toggle_id(self,vid):
        if self.busy or not vid: return
        if vid in self.selected: self.selected.remove(vid)
        else: self.selected.add(vid)
        self.row(self.records[vid])

    def toggle(self,event): self.toggle_id(self.table.identify_row(event.y))
    def toggle_keyboard(self,event):
        for vid in self.table.selection(): self.toggle_id(vid)
        return 'break'

    def select_all(self,on):
        if self.busy: return
        self.selected=set(self.records) if on else set()
        for rec in list(self.records.values()): self.row(rec)

    def filter_select(self):
        if self.busy: return
        if not self.records:
            messagebox.showinfo('Lọc video','Anh quét kênh trước khi lọc.'); return
        mode=self.filter.get()
        if mode=='Không lọc': self.select_all(True); return
        try: threshold=int(self.threshold.get().replace(',',''))
        except ValueError: messagebox.showwarning('Mức lọc','Nhập một số nguyên từ 0 trở lên.'); return
        metric='likes' if self.metric.get()=='Lượt thích' else 'views'
        try: selected,unknown=filter_records(self.records,metric,threshold,mode)
        except ValueError as exc:
            if metric=='views' and threshold>=0:
                text='Lần quét này chưa có số lượt xem để lọc. Dấu “—” không phải 0 lượt xem. Anh có thể chuyển sang Lượt thích. Các lựa chọn hiện tại được giữ nguyên.'
            else: text=str(exc)
            self.status.set(text); messagebox.showinfo('Chưa lọc được',text); return
        self.selected=selected
        for rec in list(self.records.values()): self.row(rec)
        self.status.set(f'Đã chọn {len(selected)}/{len(self.records)} video theo {self.metric.get().lower()}. {unknown} video thiếu số liệu được bỏ qua.')

    def choose_folder(self):
        if self.busy: return
        folder=filedialog.askdirectory(initialdir=self.folder.get() if Path(self.folder.get()).exists() else str(Path.home()))
        if folder: self.folder.set(folder)

    def open_folder(self):
        path=Path(self.folder.get()).expanduser()
        if path.is_dir(): os.startfile(str(path))
        else: messagebox.showinfo('Thư mục','Thư mục sẽ được tạo khi bắt đầu tải.')

    def download(self):
        if self.busy: return
        if not self.selected:
            messagebox.showinfo('Chọn video','Anh bấm từng dòng hoặc Chọn tất cả trước khi tải.'); return
        if not self.folder.get().strip():
            messagebox.showwarning('Thư mục','Chọn thư mục lưu video.'); return
        records=[self.records[v].copy() for v in self.table.get_children() if v in self.selected]
        self.progress['value']=0
        self.status.set(f'Đang tải {len(records)} video…')
        self.set_busy(True); self.engine.submit('download',records,self.folder.get())

    def cancel(self):
        self.engine.stop.set(); self.status.set('Đang dừng… kết nối đang chờ có thể cần tối đa 60 giây.')

    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='record': self.row(value)
                elif kind=='item':
                    vid,status=value
                    if vid in self.records: self.row(self.records[vid],status)
                elif kind=='status': self.status.set(value)
                elif kind=='error':
                    self.status.set('Chưa hoàn tất: '+value)
                    messagebox.showerror('Douyin Downloader',value)
                elif kind=='idle': self.set_busy(False)
                elif kind=='progress':
                    index,total,received,size=value
                    fraction=received/size if size else 1 if not received else 0
                    self.progress['value']=100*(index-1+fraction)/max(total,1)
        except queue.Empty: pass
        self.after(100,self.poll)

    def close(self):
        if self.busy and not messagebox.askyesno('Đóng app','App đang làm việc. Dừng và đóng app?'): return
        self.engine.stop.set(); self.engine.jobs.put(('quit',()))
        self.withdraw()
        self.after(200,self.wait_close)

    def wait_close(self):
        if self.engine.thread.is_alive(): self.after(200,self.wait_close)
        else: self.destroy()

if __name__=='__main__':
    if sys.platform=='win32':
        import ctypes
        try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception: pass
    App().mainloop()
