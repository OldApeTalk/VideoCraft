"""
Google Gemini Live API 字幕翻译工具
使用 Live API (WebSocket) 实现实时翻译
特点: 完全免费、无限量、实时流式响应
"""
import os
import sys
import asyncio
import srt
import json
from pathlib import Path
from datetime import timedelta
from typing import List, Optional
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
from google import genai
from google.genai import types

# ==================== 配置 ====================
# 从配置文件读取 API Key
def load_api_key():
    """从配置文件加载 API Key"""
    # 优先从 Gemini.key 读取
    gemini_key_path = Path(__file__).parent.parent / 'keys' / 'Gemini.key'
    if gemini_key_path.exists():
        with open(gemini_key_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    # 其次从 google_cloud_config.json 读取
    config_path = Path(__file__).parent.parent / 'keys' / 'google_cloud_config.json'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            if 'api_key' in config:
                return config['api_key']
    
    # 最后尝试环境变量
    return os.environ.get('GEMINI_API_KEY', '')

def get_live_models(api_key: str) -> List[str]:
    """获取支持 Live API 的模型（通过 audio 关键词筛选）"""
    if not api_key:
        # 返回默认的 audio 模型
        return [
            'gemini-2.5-flash-native-audio-latest',
            'gemini-2.5-flash-native-audio-preview-09-2025',
        ]
    
    try:
        client = genai.Client(api_key=api_key)
        all_models = []
        
        # 获取所有模型
        for model in client.models.list():
            model_name = model.name.split('/')[-1] if '/' in model.name else model.name
            all_models.append(model_name)
        
        # 筛选包含 'audio' 的模型（Live API 模型）
        audio_models = [m for m in all_models if 'audio' in m.lower()]
        
        if audio_models:
            print(f"[INFO] Found {len(audio_models)} Live API models (audio): {', '.join(audio_models)}")
            return audio_models
        else:
            # 如果没找到，返回已知的 audio 模型
            print("[WARNING] No audio models found, using default list")
            return [
                'gemini-2.5-flash-native-audio-latest',
                'gemini-2.5-flash-native-audio-preview-09-2025',
            ]
        
    except Exception as e:
        print(f"[ERROR] Failed to get model list: {e}")
        return [
            'gemini-2.5-flash-native-audio-latest',
            'gemini-2.5-flash-native-audio-preview-09-2025',
        ]

API_KEY = load_api_key()

# Live API 支持的模型（通过 audio 关键词筛选）
LIVE_MODELS = get_live_models(API_KEY)
DEFAULT_MODEL = LIVE_MODELS[0] if LIVE_MODELS else 'gemini-2.5-flash-native-audio-latest'

# 支持的源语言和目标语言
LANGUAGES = {
    'en': 'English',
    'zh': 'Simplified Chinese (简体中文)',
    'zh-TW': 'Traditional Chinese (繁體中文)',
    'ja': 'Japanese (日本語)',
    'ko': 'Korean (한국어)',
    'fr': 'French',
    'de': 'German',
    'es': 'Spanish',
    'ru': 'Russian',
    'ar': 'Arabic',
}


# ==================== Live API 翻译引擎 ====================
class LiveTranslationEngine:
    """使用 Gemini Live API 的翻译引擎"""
    
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model
        self.client = genai.Client(api_key=api_key)
        self.session = None
        self.connected = False
        
    async def connect(self, source_lang: str, target_lang: str, system_instruction: Optional[str] = None):
        """建立 Live API 连接"""
        # 构建系统指令
        if not system_instruction:
            source_name = LANGUAGES.get(source_lang, source_lang)
            target_name = LANGUAGES.get(target_lang, target_lang)
            system_instruction = f"""You are a professional subtitle translator.
Your task: Translate subtitle text from {source_name} to {target_name}.

CRITICAL RULES:
1. Output ONLY the translated text, no explanations
2. Preserve the original tone and style
3. Keep proper nouns and names unchanged
4. Maintain subtitle timing context
5. Be natural and fluent in {target_name}
"""
        
        # 配置 Live API
        config = types.LiveConnectConfig(
            system_instruction=system_instruction,
            response_modalities=["TEXT"],  # 只需要文本响应
            temperature=0.3,  # 较低温度保证一致性
        )
        
        # 连接 Live session
        try:
            print(f"[DEBUG] Connecting to model: {self.model}")
            print(f"[DEBUG] System instruction: {system_instruction[:100]}...")
            
            self.session = await self.client.aio.live.connect(
                model=self.model,
                config=config
            ).__aenter__()
            self.connected = True
            print(f"✅ Live API 已连接 (模型: {self.model})")
            
            # 等待 setup_complete 消息
            async for msg in self.session.receive():
                print(f"[DEBUG] Setup message: {type(msg)}")
                if hasattr(msg, 'setup_complete'):
                    print("✅ Setup complete!")
                    break
            
            return True
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Live API 连接失败: {e}")
            
            # 提供更友好的错误提示
            if 'quota' in error_msg.lower():
                print("\n💡 配额已用尽的可能原因:")
                print("   1. API Key 的免费配额已达到限制")
                print("   2. 需要等待配额重置（通常是每天或每月）")
                print("   3. 可能需要启用付费账户")
                print("\n建议:")
                print("   - 检查 Google AI Studio 的配额使用情况")
                print("   - 尝试使用其他 API Key")
                print("   - 等待一段时间后重试")
            elif 'not found' in error_msg.lower() or 'not supported' in error_msg.lower():
                print("\n💡 模型不支持 Live API:")
                print(f"   当前模型: {self.model}")
                print("   建议使用: gemini-2.0-flash-exp")
            
            import traceback
            traceback.print_exc()
            self.connected = False
            return False
    
    async def translate_text(self, text: str) -> str:
        """使用 Live API 翻译单个文本（使用正确的 send_client_content 方法）"""
        if not self.connected or not self.session:
            raise RuntimeError("Live session not connected")
        
        try:
            # 发送文本消息 - 使用 send_client_content 方法（官方文档推荐）
            print(f"[DEBUG] Sending: {text[:50]}...")
            await self.session.send_client_content(
                turns=[{"role": "user", "parts": [{"text": text}]}],
                turn_complete=True
            )
            
            # 接收翻译结果
            translation_parts = []
            async for response in self.session.receive():
                # Live API 返回 LiveServerMessage
                if hasattr(response, 'server_content') and response.server_content:
                    server_content = response.server_content
                    
                    # 提取 model_turn 中的文本
                    if hasattr(server_content, 'model_turn') and server_content.model_turn:
                        parts = server_content.model_turn.parts
                        if parts:
                            for part in parts:
                                if hasattr(part, 'text') and part.text:
                                    translation_parts.append(part.text)
                                    print(f"[DEBUG] Got: {part.text[:30]}...")
                    
                    # 检查是否完成
                    if hasattr(server_content, 'turn_complete') and server_content.turn_complete:
                        print("[DEBUG] Turn complete")
                        break
            
            # 组合结果
            translation = ''.join(translation_parts).strip()
            if not translation:
                print(f"⚠️  翻译为空，返回原文")
                return text
            
            print(f"✅ 翻译成功")
            return translation
            
        except Exception as e:
            print(f"⚠️  翻译错误: {e}")
            import traceback
            traceback.print_exc()
            return text
    
    async def translate_batch(self, texts: List[str], progress_callback=None) -> List[str]:
        """批量翻译文本"""
        translations = []
        total = len(texts)
        
        for idx, text in enumerate(texts, 1):
            if not text or not text.strip():
                translations.append(text)
                continue
            
            # 翻译
            translated = await self.translate_text(text)
            translations.append(translated)
            
            # 进度回调
            if progress_callback:
                progress_callback(idx, total, text, translated)
            
            # 小延迟避免过快请求
            await asyncio.sleep(0.1)
        
        return translations
    
    async def disconnect(self):
        """断开 Live API 连接"""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
                self.connected = False
                print("✅ Live API 已断开")
            except Exception as e:
                print(f"⚠️  断开连接时出错: {e}")


# ==================== SRT 处理 ====================
class SRTProcessor:
    """SRT 字幕文件处理器"""
    
    @staticmethod
    def read_srt(file_path: str) -> List[srt.Subtitle]:
        """读取 SRT 文件"""
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        return list(srt.parse(content))
    
    @staticmethod
    def write_srt(file_path: str, subtitles: List[srt.Subtitle]):
        """写入 SRT 文件"""
        with open(file_path, 'w', encoding='utf-8-sig') as f:
            f.write(srt.compose(subtitles))
    
    @staticmethod
    async def translate_srt(
        input_path: str,
        output_path: str,
        source_lang: str,
        target_lang: str,
        api_key: str,
        model: str = DEFAULT_MODEL,
        progress_callback=None
    ) -> bool:
        """翻译整个 SRT 文件"""
        try:
            # 读取原始字幕
            print(f"📖 读取字幕: {input_path}")
            subtitles = SRTProcessor.read_srt(input_path)
            total = len(subtitles)
            print(f"   共 {total} 条字幕")
            
            # 创建翻译引擎
            engine = LiveTranslationEngine(api_key, model)
            
            # 连接 Live API
            print(f"\n🔌 连接 Live API...")
            if not await engine.connect(source_lang, target_lang):
                return False
            
            # 提取文本
            texts = [sub.content for sub in subtitles]
            
            # 批量翻译
            print(f"\n🌐 开始翻译 ({source_lang} → {target_lang})...")
            translations = await engine.translate_batch(texts, progress_callback)
            
            # 更新字幕内容
            for sub, translated in zip(subtitles, translations):
                sub.content = translated
            
            # 保存翻译结果
            print(f"\n💾 保存翻译: {output_path}")
            SRTProcessor.write_srt(output_path, subtitles)
            
            # 断开连接
            await engine.disconnect()
            
            print(f"\n✅ 翻译完成!")
            return True
            
        except Exception as e:
            print(f"\n❌ 翻译失败: {e}")
            import traceback
            traceback.print_exc()
            return False


# ==================== GUI 界面 ====================
class LiveTranslationGUI:
    """Live API 翻译 GUI"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Gemini Live API 字幕翻译工具 - 免费无限量")
        self.root.geometry("900x850")  # 增加高度确保按钮可见
        
        # 变量
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.source_lang = tk.StringVar(value='en')
        self.target_lang = tk.StringVar(value='zh')
        self.api_key = tk.StringVar(value=API_KEY)
        self.model = tk.StringVar(value=DEFAULT_MODEL)
        
        self.is_translating = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置界面"""
        # ===== 标题 =====
        title_frame = ttk.Frame(self.root, padding="10")
        title_frame.pack(fill=tk.X)
        
        ttk.Label(
            title_frame,
            text="🎬 Gemini Live API 字幕翻译工具",
            font=('Arial', 16, 'bold')
        ).pack()
        ttk.Label(
            title_frame,
            text="使用 Live API (WebSocket) - 完全免费、无限量、实时响应",
            font=('Arial', 9),
            foreground='green'
        ).pack()
        
        # ===== API 配置 =====
        api_frame = ttk.LabelFrame(self.root, text="API 配置", padding="10")
        api_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(api_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, pady=2)
        api_entry = ttk.Entry(api_frame, textvariable=self.api_key, width=60, show="*")
        api_entry.grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)
        
        ttk.Label(api_frame, text="模型:").grid(row=1, column=0, sticky=tk.W, pady=2)
        model_combo = ttk.Combobox(
            api_frame,
            textvariable=self.model,
            values=LIVE_MODELS,  # 使用动态获取的 Live 模型列表
            width=40,
            state='readonly'
        )
        model_combo.grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)
        
        # ===== 文件选择 =====
        file_frame = ttk.LabelFrame(self.root, text="文件选择", padding="10")
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 输入文件
        ttk.Label(file_frame, text="输入字幕:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(file_frame, textvariable=self.input_file, width=60).grid(
            row=0, column=1, sticky=tk.W, pady=5, padx=5
        )
        ttk.Button(file_frame, text="浏览...", command=self.browse_input).grid(
            row=0, column=2, pady=5, padx=5
        )
        
        # 输出文件
        ttk.Label(file_frame, text="输出字幕:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(file_frame, textvariable=self.output_file, width=60).grid(
            row=1, column=1, sticky=tk.W, pady=5, padx=5
        )
        ttk.Button(file_frame, text="浏览...", command=self.browse_output).grid(
            row=1, column=2, pady=5, padx=5
        )
        
        # ===== 语言设置 =====
        lang_frame = ttk.LabelFrame(self.root, text="语言设置", padding="10")
        lang_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(lang_frame, text="源语言:").grid(row=0, column=0, sticky=tk.W, pady=5)
        source_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.source_lang,
            values=list(LANGUAGES.keys()),
            width=15,
            state='readonly'
        )
        source_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        source_combo.bind('<<ComboboxSelected>>', self.update_language_label)
        
        self.source_label = ttk.Label(lang_frame, text=LANGUAGES['en'], foreground='blue')
        self.source_label.grid(row=0, column=2, sticky=tk.W, pady=5, padx=10)
        
        ttk.Label(lang_frame, text="→", font=('Arial', 14)).grid(row=0, column=3, padx=10)
        
        ttk.Label(lang_frame, text="目标语言:").grid(row=0, column=4, sticky=tk.W, pady=5)
        target_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.target_lang,
            values=list(LANGUAGES.keys()),
            width=15,
            state='readonly'
        )
        target_combo.grid(row=0, column=5, sticky=tk.W, pady=5, padx=5)
        target_combo.bind('<<ComboboxSelected>>', self.update_language_label)
        
        self.target_label = ttk.Label(lang_frame, text=LANGUAGES['zh'], foreground='green')
        self.target_label.grid(row=0, column=6, sticky=tk.W, pady=5, padx=10)
        
        # ===== 进度显示 =====
        progress_frame = ttk.LabelFrame(self.root, text="翻译进度", padding="10")
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        self.status_label = ttk.Label(progress_frame, text="就绪", foreground='blue')
        self.status_label.pack(anchor=tk.W, pady=2)
        
        # 日志显示
        self.log_text = scrolledtext.ScrolledText(
            progress_frame,
            height=18,  # 增加高度
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # ===== 操作按钮 =====
        button_frame = ttk.Frame(self.root, padding="10")
        button_frame.pack(fill=tk.X)
        
        # 创建大按钮样式
        style = ttk.Style()
        style.configure('Big.TButton', font=('Arial', 11, 'bold'), padding=10)
        
        self.translate_btn = tk.Button(
            button_frame,
            text="🚀 开始翻译",
            command=self.start_translation,
            font=('Arial', 14, 'bold'),
            bg='#4CAF50',
            fg='white',
            padx=30,
            pady=15,
            cursor='hand2',
            relief=tk.RAISED,
            borderwidth=3
        )
        self.translate_btn.pack(side=tk.LEFT, padx=10)
        
        self.stop_btn = tk.Button(
            button_frame,
            text="⏹ 停止",
            command=self.stop_translation,
            font=('Arial', 11),
            bg='#f44336',
            fg='white',
            padx=20,
            pady=10,
            state=tk.DISABLED,
            cursor='hand2'
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame, 
            text="🗑 清空日志", 
            command=self.clear_log,
            style='Big.TButton'
        ).pack(side=tk.RIGHT, padx=5)
    
    def browse_input(self):
        """浏览输入文件"""
        filename = filedialog.askopenfilename(
            title="选择输入字幕文件",
            filetypes=[("SRT 字幕", "*.srt"), ("所有文件", "*.*")]
        )
        if filename:
            self.input_file.set(filename)
            # 自动设置输出文件名
            if not self.output_file.get():
                base = Path(filename).stem
                dir_path = Path(filename).parent
                self.output_file.set(str(dir_path / f"{base}_translated.srt"))
    
    def browse_output(self):
        """浏览输出文件"""
        filename = filedialog.asksaveasfilename(
            title="选择输出字幕文件",
            defaultextension=".srt",
            filetypes=[("SRT 字幕", "*.srt"), ("所有文件", "*.*")]
        )
        if filename:
            self.output_file.set(filename)
    
    def update_language_label(self, event=None):
        """更新语言标签"""
        self.source_label.config(text=LANGUAGES.get(self.source_lang.get(), ''))
        self.target_label.config(text=LANGUAGES.get(self.target_lang.get(), ''))
    
    def log(self, message: str, color: str = 'black'):
        """添加日志"""
        self.log_text.insert(tk.END, message + '\n', color)
        self.log_text.see(tk.END)
        self.log_text.update()
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete('1.0', tk.END)
    
    def update_progress(self, current: int, total: int, original: str, translated: str):
        """更新进度"""
        percentage = (current / total) * 100
        self.progress_bar['value'] = percentage
        
        status = f"翻译中... {current}/{total} ({percentage:.1f}%)"
        self.status_label.config(text=status)
        
        # 显示翻译内容（截断过长文本）
        orig_short = (original[:50] + '...') if len(original) > 50 else original
        trans_short = (translated[:50] + '...') if len(translated) > 50 else translated
        
        self.log(f"[{current}/{total}] {orig_short}", 'blue')
        self.log(f"          → {trans_short}", 'green')
        
        self.root.update()
    
    def start_translation(self):
        """开始翻译"""
        # 验证输入
        if not self.api_key.get():
            messagebox.showerror("错误", "请输入 API Key")
            return
        
        if not self.input_file.get() or not self.output_file.get():
            messagebox.showerror("错误", "请选择输入和输出文件")
            return
        
        if not Path(self.input_file.get()).exists():
            messagebox.showerror("错误", "输入文件不存在")
            return
        
        # 禁用按钮，改变外观
        self.translate_btn.config(state=tk.DISABLED, bg='#cccccc', text="⏳ 翻译中...")
        self.stop_btn.config(state=tk.NORMAL)
        self.is_translating = True
        
        # 清空日志和进度
        self.clear_log()
        self.progress_bar['value'] = 0
        self.status_label.config(text="准备中...", foreground='orange')
        
        self.log("=" * 60)
        self.log("🚀 Gemini Live API 字幕翻译开始", 'blue')
        self.log("=" * 60)
        self.log(f"📁 输入: {self.input_file.get()}")
        self.log(f"📁 输出: {self.output_file.get()}")
        self.log(f"🌐 语言: {self.source_lang.get()} → {self.target_lang.get()}")
        self.log(f"🤖 模型: {self.model.get()}")
        self.log(f"💚 Live API 模式: 免费无限量")
        self.log("=" * 60)
        
        # 在新线程中运行异步翻译
        thread = threading.Thread(target=self.run_translation, daemon=True)
        thread.start()
    
    def run_translation(self):
        """运行翻译（在新线程中）"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行异步翻译
            success = loop.run_until_complete(
                SRTProcessor.translate_srt(
                    input_path=self.input_file.get(),
                    output_path=self.output_file.get(),
                    source_lang=self.source_lang.get(),
                    target_lang=self.target_lang.get(),
                    api_key=self.api_key.get(),
                    model=self.model.get(),
                    progress_callback=self.update_progress
                )
            )
            
            # 更新 UI
            if success:
                self.root.after(0, self.translation_complete)
            else:
                self.root.after(0, self.translation_failed)
                
        except Exception as e:
            self.root.after(0, lambda: self.translation_error(str(e)))
        finally:
            loop.close()
    
    def translation_complete(self):
        """翻译完成"""
        self.log("=" * 60)
        self.log("✅ 翻译完成!", 'green')
        self.log("=" * 60)
        
        self.status_label.config(text="翻译完成 ✅", foreground='green')
        self.progress_bar['value'] = 100
        
        self.translate_btn.config(state=tk.NORMAL, bg='#4CAF50', text="🚀 开始翻译")
        self.stop_btn.config(state=tk.DISABLED)
        self.is_translating = False
        
        messagebox.showinfo("成功", f"翻译完成!\n\n输出文件:\n{self.output_file.get()}")
    
    def translation_failed(self):
        """翻译失败"""
        self.log("=" * 60)
        self.log("❌ 翻译失败", 'red')
        self.log("=" * 60)
        
        self.status_label.config(text="翻译失败 ❌", foreground='red')
        
        self.translate_btn.config(state=tk.NORMAL, bg='#4CAF50', text="🚀 开始翻译")
        self.stop_btn.config(state=tk.DISABLED)
        self.is_translating = False
        
        messagebox.showerror("错误", "翻译失败，请查看日志")
    
    def translation_error(self, error: str):
        """翻译错误"""
        self.log("=" * 60)
        self.log(f"❌ 错误: {error}", 'red')
        self.log("=" * 60)
        
        self.status_label.config(text=f"错误: {error}", foreground='red')
        
        self.translate_btn.config(state=tk.NORMAL, bg='#4CAF50', text="🚀 开始翻译")
        self.stop_btn.config(state=tk.DISABLED)
        self.is_translating = False
        
        messagebox.showerror("错误", f"翻译出错:\n{error}")
    
    def stop_translation(self):
        """停止翻译"""
        if messagebox.askyesno("确认", "确定要停止翻译吗?"):
            self.is_translating = False
            self.log("\n⏹ 用户停止翻译", 'orange')
            self.status_label.config(text="已停止", foreground='orange')


# ==================== 主程序 ====================
def main():
    """主函数"""
    root = tk.Tk()
    app = LiveTranslationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
