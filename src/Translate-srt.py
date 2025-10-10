import deepl
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import srt
import re
import requests
import time

# ===================== GUI 主界面 =====================
class TranslateApp:
    def __init__(self, master):
        self.master = master
        master.title("SRT字幕批量翻译工具（DeepL/Azure）")
        master.geometry("600x340")
        master.resizable(False, False)

        # 翻译服务选择
        tk.Label(master, text="选择翻译服务:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.service_var = tk.StringVar(value="deepl")
        self.combo = ttk.Combobox(master, textvariable=self.service_var, values=["deepl", "azure"], state="readonly", width=10)
        self.combo.grid(row=0, column=1, sticky="w")
        tk.Button(master, text="管理Key", command=self.manage_key).grid(row=0, column=2, padx=10)

        # SRT文件选择
        tk.Label(master, text="原始SRT文件:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.srt_path_var = tk.StringVar()
        tk.Entry(master, textvariable=self.srt_path_var, width=50).grid(row=1, column=1, sticky="w")
        tk.Button(master, text="浏览", command=self.select_srt).grid(row=1, column=2, padx=10)

        # 翻译按钮
        self.trans_btn = tk.Button(master, text="开始翻译", command=self.translate_srt, width=20)
        self.trans_btn.grid(row=2, column=1, pady=25)

        # 进度/提示
        self.status_var = tk.StringVar()
        tk.Label(master, textvariable=self.status_var, fg="blue").grid(row=3, column=0, columnspan=3, pady=10)

    def manage_key(self):
        service = self.service_var.get()
        if service == "deepl":
            self.configure_deepl_key()
        elif service == "azure":
            self.configure_azure_key()

    def configure_deepl_key(self):
        win = tk.Toplevel(self.master)
        win.title("DeepL API Key 配置")
        tk.Label(win, text="DeepL API Key:").pack(pady=10)
        entry = tk.Entry(win, width=50)
        entry.pack(pady=5)
        # 预填已有key
        if os.path.exists('DeepL.key'):
            with open('DeepL.key', 'r') as f:
                entry.insert(0, f.read().strip())
        def save():
            key = entry.get().strip()
            if key:
                with open('DeepL.key', 'w') as f:
                    f.write(key)
                messagebox.showinfo("Success", "API key saved!")
                win.destroy()
            else:
                messagebox.showerror("Error", "请输入有效的API key")
        tk.Button(win, text="保存", command=save).pack(pady=10)

    def configure_azure_key(self):
        win = tk.Toplevel(self.master)
        win.title("Azure API Key 配置")
        tk.Label(win, text="Azure Translator Key:").pack(pady=5)
        entry_key = tk.Entry(win, width=50)
        entry_key.pack(pady=2)
        tk.Label(win, text="Azure Endpoint (如 https://xxx.cognitiveservices.azure.com/):").pack(pady=5)
        entry_ep = tk.Entry(win, width=50)
        entry_ep.pack(pady=2)
        tk.Label(win, text="Azure 区域(region，如 westeurope, eastasia):").pack(pady=5)
        entry_region = tk.Entry(win, width=30)
        entry_region.pack(pady=2)
        # 预填已有key
        if os.path.exists('Azure.key'):
            with open('Azure.key', 'r') as f:
                lines = f.readlines()
                if len(lines) >= 3:
                    entry_key.insert(0, lines[0].strip())
                    entry_ep.insert(0, lines[1].strip())
                    entry_region.insert(0, lines[2].strip())
                elif len(lines) == 2:
                    entry_key.insert(0, lines[0].strip())
                    entry_ep.insert(0, lines[1].strip())
        def save():
            key = entry_key.get().strip()
            endpoint = entry_ep.get().strip()
            region = entry_region.get().strip()
            if key and endpoint and region:
                with open('Azure.key', 'w') as f:
                    f.write(key + '\n' + endpoint + '\n' + region)
                messagebox.showinfo("Success", "Azure key, endpoint & region saved!")
                win.destroy()
            else:
                messagebox.showerror("Error", "请输入有效的 Azure Key、Endpoint 和 Region")
        tk.Button(win, text="保存", command=save).pack(pady=10)

    def select_srt(self):
        path = filedialog.askopenfilename(title="选择SRT文件", filetypes=[("SRT files", "*.srt")])
        if path:
            self.srt_path_var.set(path)

    def translate_srt(self):
        service = self.service_var.get()
        srt_path = self.srt_path_var.get()
        if not srt_path or not os.path.exists(srt_path):
            messagebox.showerror("错误", "请选择有效的SRT文件")
            return
        self.status_var.set("正在读取字幕...")
        self.master.update()
        # 读取SRT
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                subs = list(srt.parse(f))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse SRT file: {e}")
            return
        texts = []
        placeholder = '[NL]'
        for i, sub in enumerate(subs):
            content = sub.content.replace('\n', placeholder)
            texts.append(f"{i+1}. {content}")
        full_text = '\n'.join(texts)
        self.status_var.set("正在翻译...")
        self.master.update()
        translated = None
        if service == "deepl":
            if not os.path.exists('DeepL.key'):
                messagebox.showerror("错误", "请先配置DeepL Key")
                return
            try:
                with open('DeepL.key', 'r') as f:
                    auth_key = f.read().strip()
                translator = deepl.Translator(auth_key)
                translated = translator.translate_text(
                    full_text,
                    source_lang='EN',
                    target_lang='ZH',
                    preserve_formatting=True
                ).text
            except Exception as e:
                messagebox.showerror("DeepL错误", f"翻译失败: {e}")
                return
        elif service == "azure":
            if not os.path.exists('Azure.key'):
                messagebox.showerror("错误", "请先配置Azure Key")
                return
            try:
                with open('Azure.key', 'r') as f:
                    lines = f.readlines()
                    azure_key = lines[0].strip()
                    azure_endpoint = lines[1].strip()
                    azure_region = lines[2].strip() if len(lines) >= 3 else 'global'
                # 构造 Azure API URL
                if '/translate' in azure_endpoint:
                    url = azure_endpoint.rstrip('/') + "?api-version=3.0&to=zh-Hans"
                else:
                    url = azure_endpoint.rstrip('/') + "/translate?api-version=3.0&to=zh-Hans"
                headers = {
                    'Ocp-Apim-Subscription-Key': azure_key,
                    'Ocp-Apim-Subscription-Region': azure_region,
                    'Content-type': 'application/json',
                }
                # 更健壮的分批逻辑
                translated_texts = []
                # Azure免费层限制：每分钟最多20次请求，建议每3.2秒最多1次
                REQUEST_INTERVAL = 3.5  # 秒，略大于3.2，确保安全
                batch_size = 50  # 每批最多50条，防止字符数超限
                i = 0
                def send_batch(batch):
                    resp = requests.post(url, headers=headers, json=batch)
                    print(f"Azure API status: {resp.status_code}\nResponse: {resp.text}")
                    if resp.status_code == 200:
                        return [t['translations'][0]['text'] for t in resp.json()]
                    elif resp.status_code == 429:
                        print("检测到429限流，等待30秒后重试...")
                        time.sleep(30)
                        # 重试一次
                        resp = requests.post(url, headers=headers, json=batch)
                        print(f"Azure API status: {resp.status_code}\nResponse: {resp.text}")
                        if resp.status_code == 200:
                            return [t['translations'][0]['text'] for t in resp.json()]
                        else:
                            raise Exception(f"Azure API error after retry: {resp.text}")
                    else:
                        raise Exception(f"Azure API error: {resp.text}")
                while i < len(subs):
                    batch = []
                    batch_char_count = 0
                    while i < len(subs) and len(batch) < batch_size:
                        text = subs[i].content.replace('\n', '[NL]')
                        if batch_char_count + len(text) > 4900 and batch:
                            break
                        batch.append({"Text": text})
                        batch_char_count += len(text)
                        i += 1
                    translated_texts.extend(send_batch(batch))
                    if i < len(subs):  # 最后一批不需要等待
                        time.sleep(REQUEST_INTERVAL)
                translated = translated_texts
            except Exception as e:
                print(f"Azure请求异常: {e}")
                return
        else:
            messagebox.showerror("错误", f"未知翻译服务: {service}")
            return
        # 还原字幕
        if service == "azure" and isinstance(translated, list):
            for i, sub in enumerate(subs):
                if i < len(translated):
                    sub.content = translated[i].replace('[NL]', '\n')
        else:
            pattern = re.compile(r'(\d+)\.\s*(.*?)(?=\n\d+\.|$)', re.DOTALL)
            matches = pattern.findall(translated)
            translated_subs = {}
            for match in matches:
                idx = int(match[0]) - 1
                text = match[1].strip().replace(placeholder, '\n')
                translated_subs[idx] = text
            if len(translated_subs) != len(subs):
                messagebox.showwarning("Warning", "部分字幕未能正确提取，建议检查输出。")
            for i, sub in enumerate(subs):
                if i in translated_subs:
                    sub.content = translated_subs[i]
        # 输出
        output_file = srt_path.replace('.srt', '_translated.srt')
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subs))
            self.status_var.set(f"翻译完成，已保存: {output_file}")
            messagebox.showinfo("Success", f"Translated SRT saved to: {output_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save output: {e}")
            self.status_var.set("")

# 启动主界面
if __name__ == "__main__":
    root = tk.Tk()
    app = TranslateApp(root)
    root.mainloop()