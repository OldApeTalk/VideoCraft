import deepl
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import srt
import re
import requests
import time

# 支持的语言列表 (语言代码 -> (英文名, 中文名))
SUPPORTED_LANGUAGES = {
    'auto': ('Auto Detect', '自动检测'),
    'en': ('English', '英语'),
    'zh': ('Chinese', '中文'),
    'ja': ('Japanese', '日语'),
    'ko': ('Korean', '韩语'),
    'de': ('German', '德语'),
    'fr': ('French', '法语'),
    'es': ('Spanish', '西班牙语'),
    'pt': ('Portuguese', '葡萄牙语'),
    'it': ('Italian', '意大利语'),
    'ru': ('Russian', '俄语'),
    'ar': ('Arabic', '阿拉伯语'),
    'hi': ('Hindi', '印地语'),
    'th': ('Thai', '泰语'),
    'vi': ('Vietnamese', '越南语'),
    'nl': ('Dutch', '荷兰语'),
    'pl': ('Polish', '波兰语'),
    'tr': ('Turkish', '土耳其语'),
    'sv': ('Swedish', '瑞典语'),
    'da': ('Danish', '丹麦语'),
    'no': ('Norwegian', '挪威语'),
    'fi': ('Finnish', '芬兰语'),
    'cs': ('Czech', '捷克语'),
    'hu': ('Hungarian', '匈牙利语'),
    'ro': ('Romanian', '罗马尼亚语'),
    'bg': ('Bulgarian', '保加利亚语'),
    'hr': ('Croatian', '克罗地亚语'),
    'sk': ('Slovak', '斯洛伐克语'),
    'sl': ('Slovenian', '斯洛文尼亚语'),
    'et': ('Estonian', '爱沙尼亚语'),
    'lv': ('Latvian', '拉脱维亚语'),
    'lt': ('Lithuanian', '立陶宛语'),
    'mt': ('Maltese', '马耳他语'),
    'ga': ('Irish', '爱尔兰语'),
    'is': ('Icelandic', '冰岛语'),
    'mk': ('Macedonian', '马其顿语'),
    'sq': ('Albanian', '阿尔巴尼亚语'),
    'bs': ('Bosnian', '波斯尼亚语'),
    'sr': ('Serbian', '塞尔维亚语'),
    'me': ('Montenegrin', '黑山语'),
    'uk': ('Ukrainian', '乌克兰语'),
    'be': ('Belarusian', '白俄罗斯语'),
    'ka': ('Georgian', '格鲁吉亚语'),
    'hy': ('Armenian', '亚美尼亚语'),
    'az': ('Azerbaijani', '阿塞拜疆语'),
    'kk': ('Kazakh', '哈萨克语'),
    'uz': ('Uzbek', '乌兹别克语'),
    'tk': ('Turkmen', '土库曼语'),
    'ky': ('Kyrgyz', '吉尔吉斯语'),
    'tg': ('Tajik', '塔吉克语'),
    'mn': ('Mongolian', '蒙古语'),
    'bn': ('Bengali', '孟加拉语'),
    'pa': ('Punjabi', '旁遮普语'),
    'gu': ('Gujarati', '古吉拉特语'),
    'or': ('Oriya', '奥里亚语'),
    'te': ('Telugu', '泰卢固语'),
    'kn': ('Kannada', '卡纳达语'),
    'ml': ('Malayalam', '马拉雅拉姆语'),
    'si': ('Sinhala', '僧伽罗语'),
    'ne': ('Nepali', '尼泊尔语'),
    'mr': ('Marathi', '马拉地语'),
    'as': ('Assamese', '阿萨姆语'),
    'bh': ('Bihari', '比哈里语'),
    'sa': ('Sanskrit', '梵语'),
    'sd': ('Sindhi', '信德语'),
    'ur': ('Urdu', '乌尔都语'),
    'fa': ('Persian', '波斯语'),
    'he': ('Hebrew', '希伯来语'),
    'yi': ('Yiddish', '意第绪语'),
    'am': ('Amharic', '阿姆哈拉语'),
    'ti': ('Tigrinya', '提格里尼亚语'),
    'om': ('Oromo', '奥罗莫语'),
    'so': ('Somali', '索马里语'),
    'sw': ('Swahili', '斯瓦希里语'),
    'rw': ('Kinyarwanda', '卢旺达语'),
    'rn': ('Kirundi', '基隆迪语'),
    'mg': ('Malagasy', '马达加斯加语'),
    'xh': ('Xhosa', '科萨语'),
    'zu': ('Zulu', '祖鲁语'),
    'st': ('Sesotho', '塞索托语'),
    'tn': ('Tswana', '茨瓦纳语'),
    'af': ('Afrikaans', '南非荷兰语'),
    'ha': ('Hausa', '豪萨语'),
    'yo': ('Yoruba', '约鲁巴语'),
    'ig': ('Igbo', '伊博语'),
    'id': ('Indonesian', '印度尼西亚语'),
    'ms': ('Malay', '马来语'),
    'tl': ('Filipino', '菲律宾语'),
    'jv': ('Javanese', '爪哇语'),
    'su': ('Sundanese', '巽他语'),
    'ceb': ('Cebuano', '宿务语'),
    'ilo': ('Iloko', '伊洛卡诺语'),
    'bi': ('Bislama', '比斯拉马语'),
    'to': ('Tonga', '汤加语'),
    'sm': ('Samoan', '萨摩亚语'),
    'haw': ('Hawaiian', '夏威夷语'),
    'fj': ('Fijian', '斐济语'),
    'mh': ('Marshallese', '马绍尔语'),
    'ty': ('Tahitian', '塔希提语'),
    'el': ('Greek', '希腊语'),
    'la': ('Latin', '拉丁语'),
    'cy': ('Welsh', '威尔士语'),
    'eu': ('Basque', '巴斯克语'),
    'ca': ('Catalan', '加泰罗尼亚语'),
    'gl': ('Galician', '加利西亚语'),
    'eo': ('Esperanto', '世界语'),
    'my': ('Burmese', '缅甸语'),
    'km': ('Khmer', '高棉语'),
    'lo': ('Lao', '老挝语'),
    'bo': ('Tibetan', '藏语'),
    'dz': ('Dzongkha', '宗喀语'),
    'si': ('Sinhala', '僧伽罗语'),
    'pi': ('Pali', '巴利语'),
}

# Azure语言代码映射 (ISO -> Azure格式)
AZURE_LANG_MAP = {
    'zh': 'zh-Hans',  # 简体中文
    'zh-cn': 'zh-Hans',
    'zh-tw': 'zh-Hant',  # 繁体中文
    'zh-hk': 'zh-Hant',
    'pt': 'pt-pt',  # 葡萄牙语(葡萄牙)
    'pt-br': 'pt-br',  # 葡萄牙语(巴西)
    'en': 'en',
    'ja': 'ja',
    'ko': 'ko',
    'de': 'de',
    'fr': 'fr',
    'es': 'es',
    'it': 'it',
    'ru': 'ru',
    'ar': 'ar',
    'hi': 'hi',
    'th': 'th',
    'vi': 'vi',
    'nl': 'nl',
    'pl': 'pl',
    'tr': 'tr',
    'sv': 'sv',
    'da': 'da',
    'no': 'nb',  # 挪威语(书面)
    'fi': 'fi',
    'cs': 'cs',
    'hu': 'hu',
    'ro': 'ro',
    'bg': 'bg',
    'hr': 'hr',
    'sk': 'sk',
    'sl': 'sl',
    'et': 'et',
    'lv': 'lv',
    'lt': 'lt',
    'mt': 'mt',
    'ga': 'ga',
    'is': 'is',
    'mk': 'mk',
    'sq': 'sq',
    'bs': 'bs',
    'sr': 'sr',
    'me': 'sr',  # 黑山语 -> 塞尔维亚语
    'uk': 'uk',
    'be': 'be',
    'ka': 'ka',
    'hy': 'hy',
    'az': 'az',
    'kk': 'kk',
    'uz': 'uz',
    'tk': 'tk',
    'ky': 'ky',
    'tg': 'tg',
    'mn': 'mn',
    'bn': 'bn',
    'pa': 'pa',
    'gu': 'gu',
    'or': 'or',
    'te': 'te',
    'kn': 'kn',
    'ml': 'ml',
    'si': 'si',
    'ne': 'ne',
    'mr': 'mr',
    'as': 'as',
    'sa': 'sa',
    'sd': 'sd',
    'ur': 'ur',
    'fa': 'fa',
    'he': 'he',
    'yi': 'yi',
    'am': 'am',
    'ti': 'ti',
    'om': 'om',
    'so': 'so',
    'sw': 'sw',
    'rw': 'rw',
    'rn': 'rn',
    'mg': 'mg',
    'xh': 'xh',
    'zu': 'zu',
    'st': 'st',
    'tn': 'tn',
    'af': 'af',
    'ha': 'ha',
    'yo': 'yo',
    'ig': 'ig',
    'id': 'id',
    'ms': 'ms',
    'tl': 'tl',
    'jv': 'jv',
    'su': 'su',
    'ceb': 'ceb',
    'ilo': 'ilo',
    'bi': 'bi',
    'to': 'to',
    'sm': 'sm',
    'haw': 'haw',
    'fj': 'fj',
    'mh': 'mh',
    'ty': 'ty',
    'el': 'el',
    'la': 'la',
    'cy': 'cy',
    'eu': 'eu',
    'ca': 'ca',
    'gl': 'gl',
    'eo': 'eo',
    'my': 'my',
    'km': 'km',
    'lo': 'lo',
    'bo': 'bo',
    'dz': 'dz',
    'pi': 'pi',
}

# 生成语言选项列表
language_options = []
for code, (eng, chn) in SUPPORTED_LANGUAGES.items():
    language_options.append(f"{eng} ({chn}) - {code.upper()}")

# ===================== GUI 主界面 =====================
class TranslateApp:
    def __init__(self, master):
        self.master = master
        master.title("SRT字幕批量翻译工具（DeepL/Azure）")
        master.geometry("700x420")
        master.resizable(False, False)

        # 翻译服务选择
        tk.Label(master, text="选择翻译服务:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.service_var = tk.StringVar(value="deepl")
        self.combo = ttk.Combobox(master, textvariable=self.service_var, values=["deepl", "azure"], state="readonly", width=10)
        self.combo.grid(row=0, column=1, sticky="w")
        tk.Button(master, text="管理Key", command=self.manage_key).grid(row=0, column=2, padx=10)

        # 源语言选择
        tk.Label(master, text="源语言 (Source):").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.source_lang_var = tk.StringVar(value="English (英语) - EN")
        self.source_combo = ttk.Combobox(master, textvariable=self.source_lang_var, values=language_options, state="readonly", width=30)
        self.source_combo.grid(row=1, column=1, columnspan=2, sticky="w", padx=(0,10))

        # 目标语言选择
        tk.Label(master, text="目标语言 (Target):").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.target_lang_var = tk.StringVar(value="Chinese (中文) - ZH")
        self.target_combo = ttk.Combobox(master, textvariable=self.target_lang_var, values=language_options, state="readonly", width=30)
        self.target_combo.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0,10))

        # SRT文件选择
        tk.Label(master, text="原始SRT文件:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
        self.srt_path_var = tk.StringVar()
        tk.Entry(master, textvariable=self.srt_path_var, width=50).grid(row=3, column=1, sticky="w")
        tk.Button(master, text="浏览", command=self.select_srt).grid(row=3, column=2, padx=10)

        # 翻译按钮
        self.trans_btn = tk.Button(master, text="开始翻译", command=self.translate_srt, width=20)
        self.trans_btn.grid(row=4, column=1, pady=25)

        # 进度/提示
        self.status_var = tk.StringVar()
        tk.Label(master, textvariable=self.status_var, fg="blue").grid(row=5, column=0, columnspan=3, pady=10)

    def get_lang_code(self, lang_str):
        """从语言选择字符串中提取语言代码"""
        if " - " in lang_str:
            code = lang_str.split(" - ")[-1].lower()
            if code in SUPPORTED_LANGUAGES:
                return code
        return 'en'  # 默认返回英语

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
        deepl_key_path = os.path.join('..', 'keys', 'DeepL.key')
        if os.path.exists(deepl_key_path):
            with open(deepl_key_path, 'r') as f:
                entry.insert(0, f.read().strip())
        def save():
            key = entry.get().strip()
            if key:
                deepl_key_path = os.path.join('..', 'keys', 'DeepL.key')
                # 确保keys文件夹存在
                os.makedirs(os.path.dirname(deepl_key_path), exist_ok=True)
                with open(deepl_key_path, 'w') as f:
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
        source_lang = self.get_lang_code(self.source_lang_var.get())
        target_lang = self.get_lang_code(self.target_lang_var.get())
        
        if not srt_path or not os.path.exists(srt_path):
            messagebox.showerror("错误", "请选择有效的SRT文件")
            return
        
        if source_lang == target_lang:
            messagebox.showerror("错误", "源语言和目标语言不能相同")
            return
            
        # 验证语言支持
        if service == "deepl":
            # DeepL支持的主要语言
            deepl_supported = ['en', 'de', 'fr', 'es', 'pt', 'it', 'nl', 'pl', 'ru', 'ja', 'zh', 'auto']
            if source_lang not in deepl_supported and source_lang != 'auto':
                messagebox.showerror("错误", f"DeepL不支持源语言: {source_lang.upper()}")
                return
            if target_lang not in deepl_supported:
                messagebox.showerror("错误", f"DeepL不支持目标语言: {target_lang.upper()}")
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
        self.status_var.set(f"正在翻译 ({source_lang.upper()} -> {target_lang.upper()})...")
        self.master.update()
        
        translated = None
        if service == "deepl":
            deepl_key_path = os.path.join('..', 'keys', 'DeepL.key')
            if not os.path.exists(deepl_key_path):
                messagebox.showerror("错误", "请先配置DeepL Key")
                return
            try:
                with open(deepl_key_path, 'r') as f:
                    auth_key = f.read().strip()
                translator = deepl.Translator(auth_key)
                
                # DeepL语言代码转换
                deepl_source = source_lang.upper() if source_lang != 'auto' else None
                deepl_target = target_lang.upper()
                
                translated = translator.translate_text(
                    full_text,
                    source_lang=deepl_source,
                    target_lang=deepl_target,
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
                azure_target = AZURE_LANG_MAP.get(target_lang, target_lang)
                if '/translate' in azure_endpoint:
                    url = azure_endpoint.rstrip('/') + f"?api-version=3.0&to={azure_target}"
                else:
                    url = azure_endpoint.rstrip('/') + f"/translate?api-version=3.0&to={azure_target}"
                
                if source_lang != 'auto':
                    azure_source = AZURE_LANG_MAP.get(source_lang, source_lang)
                    url += f"&from={azure_source}"
                
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
        target_lang_name = SUPPORTED_LANGUAGES[target_lang][0]  # 获取目标语言的英文名
        output_dir = os.path.dirname(srt_path)  # 获取原文件的目录
        output_file = os.path.join(output_dir, f"{target_lang_name}.srt")
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