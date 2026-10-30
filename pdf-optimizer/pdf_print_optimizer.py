# coding: utf-8
"""A4 nesting sheet optimizer. Crops original PDF regions; does not alter production values."""
from pathlib import Path
import queue, threading
import fitz
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

REGIONS = {
    "title": ((90,10,510,75),(70,12,510,77)),
    "date": ((515,10,585,37),(495,10,580,40)),
    "top": ((92,77,508,204),(17,87,578,267)),
    "drawing": ((29,209,559,307),(22,281,573,394)),
    "bottom": ((29,315,570,456),(22,408,573,568)),
}
def convert(source, output):
    doc=fitz.open(str(source))
    if doc.needs_pass:
        doc.close()
        raise ValueError("PDF 已加密")
    result=fitz.open()
    try:
        for page in doc:
            if abs(page.rect.width-595)>4 or abs(page.rect.height-842)>4:
                raise ValueError("源文件不是预期的 A4 竖版模板，已停止以避免错误裁剪")
            if len(page.get_text().strip())>100:
                raise ValueError("检测到可提取文本，版式可能不同；已停止以避免错误裁剪")
            out=result.new_page(width=595,height=842)
            for name,(src,dst) in REGIONS.items():
                pix=page.get_pixmap(matrix=fitz.Matrix(3,3),clip=fitz.Rect(*src),alpha=False)
                out.insert_image(fitz.Rect(*dst),stream=pix.tobytes("png"),keep_proportion=True)
        result.save(str(output),garbage=4,deflate=True)
    finally:
        doc.close()
        result.close()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF 套料单打印优化助手")
        self.geometry("780x540")
        self.files=[]
        self.events=queue.Queue()
        self.busy=False
        ttk.Label(self,text="套料单 A4 竖版打印优化",font=("Microsoft YaHei UI",17,"bold")).pack(pady=12)
        ttk.Label(self,text="固定样本版式 · 保留原始数字 · 输出新 PDF 不覆盖源文件").pack()
        bar=ttk.Frame(self)
        bar.pack(pady=12)
        for label,fn in [("添加 PDF",self.add),("添加文件夹",self.add_folder),("清空",self.clear),("预览选中",self.preview)]:
            ttk.Button(bar,text=label,command=fn).pack(side="left",padx=4)
        self.listbox=tk.Listbox(self,selectmode="extended")
        self.listbox.pack(fill="both",expand=True,padx=20)
        self.status=tk.StringVar(value="添加 PDF 后先预览，再批量处理。")
        ttk.Label(self,textvariable=self.status,wraplength=730).pack(padx=20,pady=8)
        ttk.Label(self,text="注意：仅适用于与原始样本版式一致的文件；图片放大不等于真正修改字体。").pack()
        self.progress=ttk.Progressbar(self,mode="determinate")
        self.progress.pack(fill="x",padx=20,pady=10)
        ttk.Button(self,text="批量生成 A4 PDF",command=self.start).pack(pady=8)
        self.after(120,self.poll)
    def add_one(self,path):
        p=Path(path)
        if p not in self.files:
            self.files.append(p)
            self.listbox.insert("end",str(p))
    def add(self):
        for p in filedialog.askopenfilenames(filetypes=[("PDF","*.pdf")]):
            self.add_one(p)
    def add_folder(self):
        folder=filedialog.askdirectory()
        if folder:
            for p in sorted(Path(folder).glob("*.pdf")):
                self.add_one(p)
    def clear(self):
        if self.busy:return
        self.files.clear()
        self.listbox.delete(0,"end")
    def preview(self):
        sel=self.listbox.curselection()
        if not sel:return messagebox.showinfo("提示","请先选择一份 PDF")
        p=self.files[sel[0]]
        try:
            import tempfile, os
            out=Path(tempfile.gettempdir())/(p.stem+"_A4_preview.pdf")
            convert(p,out)
            os.startfile(str(out))
        except Exception as e:
            messagebox.showerror("预览失败",str(e))
    def start(self):
        if self.busy or not self.files:return
        self.busy=True
        self.progress["maximum"]=len(self.files)
        self.progress["value"]=0
        threading.Thread(target=self.worker,daemon=True).start()
    def worker(self):
        success=0
        errors=[]
        for i,p in enumerate(self.files):
            try:
                folder=p.parent/"optimized"
                folder.mkdir(exist_ok=True)
                convert(p,folder/(p.stem+"_A4.pdf"))
                success+=1
            except Exception as e:
                errors.append(f"{p.name}: {e}")
            self.events.put(("progress",i+1))
        self.events.put(("done",success,errors))
    def poll(self):
        try:
            while True:
                ev=self.events.get_nowait()
                if ev[0]=="progress":
                    self.progress["value"]=ev[1]
                    self.status.set(f"处理进度：{ev[1]}/{len(self.files)}")
                else:
                    self.busy=False
                    self.status.set(f"成功 {ev[1]} 份；失败 {len(ev[2])} 份。输出位于各源文件旁 optimized 文件夹。")
                    messagebox.showinfo("处理结果",self.status.get()+("\n\n"+"\n".join(ev[2][:8]) if ev[2] else ""))
        except queue.Empty:
            pass
        self.after(120,self.poll)
if __name__=="__main__":
    App().mainloop()
