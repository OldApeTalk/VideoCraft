import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json
import threading
import subprocess
from google.cloud import texttospeech
from google.oauth2 import service_account

class Text2VideoApp:
    def __init__(self, master):
        self.master = master
        master.title("VideoCraft - 语音合成与视频制作")
        master.geometry("1100x750")
        master.resizable(True, True)

        # 创建 Notebook (标签页)
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # 标签页1: 文本转音频
        self.tab_text2audio = tk.Frame(self.notebook)
        self.notebook.add(self.tab_text2audio, text="文本转音频 (Gemini-TTS)")

        # 标签页2: 音频合成视频
        self.tab_audio2video = tk.Frame(self.notebook)
        self.notebook.add(self.tab_audio2video, text="音频合成视频")

        # 初始化各个标签页
        self.init_text2audio_tab()
        self.init_audio2video_tab()

        # 加载配置
        self.config = {}
        self.load_cloud_config()

    def init_text2audio_tab(self):
        """初始化文本转音频标签页"""
        tab = self.tab_text2audio

        # Google Cloud 配置状态显示
        tk.Label(tab, text="配置状态:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.config_status_var = tk.StringVar(value="未配置")
        tk.Label(tab, textvariable=self.config_status_var, fg="red").grid(row=0, column=1, sticky="w")
        tk.Button(tab, text="管理配置", command=self.configure_cloud_settings).grid(row=0, column=2, padx=10)

        # API密钥状态
        tk.Label(tab, text="API密钥:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.account_status_var = tk.StringVar(value="未配置")
        tk.Label(tab, textvariable=self.account_status_var, fg="red").grid(row=1, column=1, sticky="w")

        # 输入文本
        tk.Label(tab, text="输入文本:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        self.input_text = tk.Text(tab, height=8, width=50, wrap=tk.WORD)
        self.input_text.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0,10))
        # 设置默认文本
        default_text = "欢迎使用文本到语音工具。这是一个测试文本，用于演示如何将文本转换为语音。"
        self.input_text.insert(tk.END, default_text)

        # 输出文件选择
        tk.Label(tab, text="输出文件:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
        self.output_path_var = tk.StringVar(value="output.mp3")
        tk.Entry(tab, textvariable=self.output_path_var, width=50).grid(row=3, column=1, sticky="w")
        tk.Button(tab, text="浏览", command=self.select_output).grid(row=3, column=2, padx=10)

        # Gemini-TTS 模型选择
        tk.Label(tab, text="Gemini 模型:").grid(row=4, column=0, padx=10, pady=5, sticky="e")
        self.model_var = tk.StringVar(value="gemini-2.5-pro-tts (高质量)")
        model_options = [
            "gemini-2.5-flash-tts (推荐)",
            "gemini-2.5-pro-tts (高质量)",
            "gemini-2.5-flash-lite-tts (快速)"
        ]
        self.model_combo = ttk.Combobox(tab, textvariable=self.model_var, values=model_options, state="readonly", width=25)
        self.model_combo.grid(row=4, column=1, sticky="w", padx=(0,10))
        self.model_combo.bind('<<ComboboxSelected>>', self.on_model_change)

        # 语言选择
        tk.Label(tab, text="语言:").grid(row=5, column=0, padx=10, pady=5, sticky="e")
        self.lang_var = tk.StringVar(value="cmn-CN")
        lang_options = [
            "cmn-CN (普通话)",
            "en-US (美国英语)",
            "en-GB (英国英语)",
            "ja-JP (日语)",
            "ko-KR (韩语)",
            "fr-FR (法语)",
            "de-DE (德语)",
            "es-ES (西班牙语)"
        ]
        self.lang_combo = ttk.Combobox(tab, textvariable=self.lang_var, values=lang_options, state="readonly", width=20)
        self.lang_combo.grid(row=5, column=1, sticky="w", padx=(0,10))
        self.lang_combo.bind('<<ComboboxSelected>>', self.on_language_change)

        # 声音选择
        tk.Label(tab, text="声音:").grid(row=6, column=0, padx=10, pady=5, sticky="e")
        self.voice_var = tk.StringVar(value="Charon")
        self.voice_combo = ttk.Combobox(tab, textvariable=self.voice_var, state="readonly", width=20)
        self.voice_combo.grid(row=6, column=1, sticky="w", padx=(0,10))
        
        # 初始化声音选项
        self.update_voice_options()
        
        # Prompt 输入框和预设按钮（Gemini-TTS 新功能）
        prompt_frame = tk.Frame(tab)
        prompt_frame.grid(row=7, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        
        tk.Label(prompt_frame, text="Prompt:").pack(side=tk.LEFT, padx=(0,5))
        self.prompt_var = tk.StringVar(value="用生动、富有表现力的语气讲故事")
        self.prompt_entry = tk.Entry(prompt_frame, textvariable=self.prompt_var, width=45)
        self.prompt_entry.pack(side=tk.LEFT, padx=5)
        
        # 预设风格按钮
        preset_btn = tk.Button(prompt_frame, text="预设风格▼", command=self.show_prompt_presets, width=10)
        preset_btn.pack(side=tk.LEFT, padx=5)

        # 语速控制
        tk.Label(tab, text="语速:").grid(row=8, column=0, padx=10, pady=5, sticky="e")
        speed_frame = tk.Frame(tab)
        speed_frame.grid(row=8, column=1, columnspan=2, sticky="w")
        self.speed_var = tk.DoubleVar(value=1.25)
        self.speed_scale = tk.Scale(speed_frame, from_=0.25, to=4.0, resolution=0.05, orient=tk.HORIZONTAL,
                                     variable=self.speed_var, length=200)
        self.speed_scale.pack(side=tk.LEFT)
        self.speed_label = tk.Label(speed_frame, text="1.25x")
        self.speed_label.pack(side=tk.LEFT, padx=5)
        self.speed_var.trace('w', lambda *args: self.speed_label.config(text=f"{self.speed_var.get():.2f}x"))

        # 音调控制
        tk.Label(tab, text="音调:").grid(row=9, column=0, padx=10, pady=5, sticky="e")
        pitch_frame = tk.Frame(tab)
        pitch_frame.grid(row=9, column=1, columnspan=2, sticky="w")
        self.pitch_var = tk.DoubleVar(value=0.0)
        self.pitch_scale = tk.Scale(pitch_frame, from_=-20.0, to=20.0, resolution=0.5, orient=tk.HORIZONTAL,
                                     variable=self.pitch_var, length=200)
        self.pitch_scale.pack(side=tk.LEFT)
        self.pitch_label = tk.Label(pitch_frame, text="0.0")
        self.pitch_label.pack(side=tk.LEFT, padx=5)
        self.pitch_var.trace('w', lambda *args: self.pitch_label.config(text=f"{self.pitch_var.get():.1f}"))

        # 音量增益控制
        tk.Label(tab, text="音量增益:").grid(row=10, column=0, padx=10, pady=5, sticky="e")
        volume_frame = tk.Frame(tab)
        volume_frame.grid(row=10, column=1, columnspan=2, sticky="w")
        self.volume_var = tk.DoubleVar(value=0.0)
        self.volume_scale = tk.Scale(volume_frame, from_=-96.0, to=16.0, resolution=1.0, orient=tk.HORIZONTAL,
                                      variable=self.volume_var, length=200)
        self.volume_scale.pack(side=tk.LEFT)
        self.volume_label = tk.Label(volume_frame, text="0.0 dB")
        self.volume_label.pack(side=tk.LEFT, padx=5)
        self.volume_var.trace('w', lambda *args: self.volume_label.config(text=f"{self.volume_var.get():.1f} dB"))

        # 音频格式选择
        tk.Label(tab, text="音频格式:").grid(row=11, column=0, padx=10, pady=5, sticky="e")
        self.format_var = tk.StringVar(value="MP3")
        format_options = ["MP3", "WAV", "OGG_OPUS"]
        self.format_combo = ttk.Combobox(tab, textvariable=self.format_var, values=format_options, state="readonly", width=15)
        self.format_combo.grid(row=11, column=1, sticky="w", padx=(0,10))

        # 生成按钮
        self.generate_btn = tk.Button(tab, text="生成语音 (Gemini-TTS)", command=self.start_generation, width=25)
        self.generate_btn.grid(row=12, column=1, pady=20)

        # 进度/提示
        self.status_var = tk.StringVar()
        tk.Label(tab, textvariable=self.status_var, fg="blue").grid(row=13, column=0, columnspan=3, pady=10)

    def init_audio2video_tab(self):
        """初始化音频合成视频标签页 - 左右分栏布局"""
        tab = self.tab_audio2video
        
        # 创建左右两个主框架
        left_frame = tk.Frame(tab)
        left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        right_frame = tk.Frame(tab)
        right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        # 配置列权重，使两列均匀分布
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)
        
        # ========== 左侧：文件选择和视频参数 ==========
        # 文件选择分组
        file_frame = tk.LabelFrame(left_frame, text="文件选择", padx=10, pady=10)
        file_frame.pack(fill="both", padx=5, pady=5)
        
        # 音频文件选择
        tk.Label(file_frame, text="音频文件:").grid(row=0, column=0, padx=5, pady=8, sticky="e")
        self.audio_path_var = tk.StringVar(value="")
        tk.Entry(file_frame, textvariable=self.audio_path_var, width=45, state='readonly').grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(file_frame, text="选择", command=self.select_audio_file, width=8).grid(row=0, column=2, padx=5)
        
        # 音频信息
        self.audio_info_var = tk.StringVar(value="未选择音频文件")
        tk.Label(file_frame, textvariable=self.audio_info_var, fg="gray", font=("Arial", 8)).grid(row=1, column=1, sticky="w", padx=5)
        
        # 图片文件选择
        tk.Label(file_frame, text="图片文件:").grid(row=2, column=0, padx=5, pady=8, sticky="e")
        self.image_path_var = tk.StringVar(value="")
        tk.Entry(file_frame, textvariable=self.image_path_var, width=45, state='readonly').grid(row=2, column=1, sticky="ew", padx=5)
        tk.Button(file_frame, text="选择", command=self.select_image_file, width=8).grid(row=2, column=2, padx=5)
        
        # 图片信息
        self.image_info_var = tk.StringVar(value="未选择图片文件")
        tk.Label(file_frame, textvariable=self.image_info_var, fg="gray", font=("Arial", 8)).grid(row=3, column=1, sticky="w", padx=5)
        
        # 输出视频
        tk.Label(file_frame, text="输出视频:").grid(row=4, column=0, padx=5, pady=8, sticky="e")
        self.video_output_var = tk.StringVar(value="output.mp4")
        tk.Entry(file_frame, textvariable=self.video_output_var, width=45).grid(row=4, column=1, sticky="ew", padx=5)
        tk.Button(file_frame, text="浏览", command=self.select_video_output, width=8).grid(row=4, column=2, padx=5)
        
        # 让第1列（输入框列）自动扩展
        file_frame.columnconfigure(1, weight=1)
        
        # 视频配置分组
        config_frame = tk.LabelFrame(left_frame, text="视频配置", padx=10, pady=10)
        config_frame.pack(fill="both", padx=5, pady=5)
        
        # 视频方向
        tk.Label(config_frame, text="视频方向:", font=("Arial", 9, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.orientation_var = tk.StringVar(value="horizontal")
        orientation_inner = tk.Frame(config_frame)
        orientation_inner.grid(row=0, column=1, columnspan=2, sticky="w", padx=5)
        tk.Radiobutton(orientation_inner, text="横屏 (16:9)", variable=self.orientation_var, 
                      value="horizontal", command=self.on_orientation_change).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(orientation_inner, text="竖屏 (9:16)", variable=self.orientation_var, 
                      value="vertical", command=self.on_orientation_change).pack(side=tk.LEFT, padx=5)
        
        # 分辨率
        tk.Label(config_frame, text="分辨率:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.resolution_var = tk.StringVar(value="1920x1080 (1080p)")
        self.resolution_combo = ttk.Combobox(config_frame, textvariable=self.resolution_var, state="readonly", width=30)
        self.update_resolution_options()
        self.resolution_combo.grid(row=1, column=1, columnspan=2, sticky="w", padx=5)
        
        # 背景填充色
        tk.Label(config_frame, text="背景填充色:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        bg_color_inner = tk.Frame(config_frame)
        bg_color_inner.grid(row=2, column=1, columnspan=2, sticky="w", padx=5)
        self.bg_color_var = tk.StringVar(value="#FFFFFF")
        self.bg_color_entry = tk.Entry(bg_color_inner, textvariable=self.bg_color_var, width=10, state='readonly')
        self.bg_color_entry.pack(side=tk.LEFT, padx=2)
        self.bg_color_preview = tk.Canvas(bg_color_inner, width=25, height=20, bg=self.bg_color_var.get(), relief=tk.SUNKEN, borderwidth=1)
        self.bg_color_preview.pack(side=tk.LEFT, padx=2)
        self.bg_color_btn = tk.Button(bg_color_inner, text="选择", command=self.choose_bg_color, width=8)
        self.bg_color_btn.pack(side=tk.LEFT, padx=2)
        
        # 帧率
        tk.Label(config_frame, text="帧率 (FPS):").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.fps_var = tk.StringVar(value="30")
        fps_options = ["24", "25", "30", "60"]
        self.fps_combo = ttk.Combobox(config_frame, textvariable=self.fps_var, values=fps_options, state="readonly", width=10)
        self.fps_combo.grid(row=3, column=1, sticky="w", padx=5)
        
        # 视频编码
        tk.Label(config_frame, text="视频编码:").grid(row=4, column=0, padx=5, pady=5, sticky="e")
        self.codec_var = tk.StringVar(value="libx264")
        codec_options = ["libx264 (H.264)", "libx265 (H.265/HEVC)", "mpeg4"]
        self.codec_combo = ttk.Combobox(config_frame, textvariable=self.codec_var, values=codec_options, state="readonly", width=25)
        self.codec_combo.grid(row=4, column=1, columnspan=2, sticky="w", padx=5)
        
        # ========== 右侧：水印设置 ==========
        watermark_frame = tk.LabelFrame(right_frame, text="水印设置", padx=10, pady=10)
        watermark_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 启用水印
        self.watermark_enabled_var = tk.BooleanVar(value=True)
        tk.Checkbutton(watermark_frame, text="启用水印", variable=self.watermark_enabled_var, 
                      font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, padx=5, pady=10, sticky="w")
        
        # 水印文字
        tk.Label(watermark_frame, text="水印文字:").grid(row=1, column=0, padx=5, pady=8, sticky="e")
        self.watermark_text_var = tk.StringVar(value="老猿世界观察")
        tk.Entry(watermark_frame, textvariable=self.watermark_text_var, width=35).grid(row=1, column=1, columnspan=2, sticky="ew", padx=5)
        
        # 让第1列自动扩展
        watermark_frame.columnconfigure(1, weight=1)
        
        # 文字颜色
        tk.Label(watermark_frame, text="文字颜色:").grid(row=2, column=0, padx=5, pady=8, sticky="e")
        wm_color_inner = tk.Frame(watermark_frame)
        wm_color_inner.grid(row=2, column=1, columnspan=2, sticky="w", padx=5)
        self.watermark_color_var = tk.StringVar(value="#80ffff")
        self.watermark_color_entry = tk.Entry(wm_color_inner, textvariable=self.watermark_color_var, width=10, state='readonly')
        self.watermark_color_entry.pack(side=tk.LEFT, padx=2)
        self.watermark_color_preview = tk.Canvas(wm_color_inner, width=25, height=20, bg=self.watermark_color_var.get(), relief=tk.SUNKEN, borderwidth=1)
        self.watermark_color_preview.pack(side=tk.LEFT, padx=2)
        self.watermark_color_btn = tk.Button(wm_color_inner, text="选择", command=self.choose_watermark_color, width=8)
        self.watermark_color_btn.pack(side=tk.LEFT, padx=2)
        
        # 字体
        tk.Label(watermark_frame, text="字体:").grid(row=3, column=0, padx=5, pady=8, sticky="e")
        self.watermark_font_var = tk.StringVar(value="simsun.ttc (宋体)")
        font_options = ["arial.ttf", "simhei.ttf (黑体)", "simsun.ttc (宋体)", "msyh.ttc (微软雅黑)", "simkai.ttf (楷体)"]
        self.watermark_font_combo = ttk.Combobox(watermark_frame, textvariable=self.watermark_font_var, values=font_options, width=32)
        self.watermark_font_combo.grid(row=3, column=1, columnspan=2, sticky="ew", padx=5)
        
        # 透明度
        tk.Label(watermark_frame, text="透明度:").grid(row=4, column=0, padx=5, pady=8, sticky="e")
        self.watermark_opacity_var = tk.DoubleVar(value=0.5)
        opacity_scale = tk.Scale(watermark_frame, from_=0.1, to=1.0, resolution=0.1, orient=tk.HORIZONTAL, 
                                variable=self.watermark_opacity_var, length=260)
        opacity_scale.grid(row=4, column=1, columnspan=2, sticky="ew", padx=5)
        
        # 位置
        tk.Label(watermark_frame, text="位置:").grid(row=5, column=0, padx=5, pady=8, sticky="e")
        self.watermark_position_var = tk.StringVar(value="右上角 (topright)")
        position_options = ["右上角 (topright)", "左上角 (topleft)", "右下角 (bottomright)", "左下角 (bottomleft)"]
        self.watermark_position_combo = ttk.Combobox(watermark_frame, textvariable=self.watermark_position_var, 
                                                      values=position_options, state="readonly", width=30)
        self.watermark_position_combo.grid(row=5, column=1, columnspan=2, sticky="ew", padx=5)
        
        # ========== 底部：生成按钮和状态 ==========
        bottom_frame = tk.Frame(tab)
        bottom_frame.grid(row=1, column=0, columnspan=2, pady=10)
        
        # 生成按钮
        self.generate_video_btn = tk.Button(bottom_frame, text="生成视频", command=self.start_video_generation, 
                                           width=25, height=2, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"))
        self.generate_video_btn.pack(pady=10)
        
        # 进度显示
        self.video_status_var = tk.StringVar(value="")
        tk.Label(bottom_frame, textvariable=self.video_status_var, fg="blue", font=("Arial", 10)).pack(pady=5)

    def load_cloud_config(self):
        """加载Google Cloud配置，使用服务账户密钥文件"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file = os.path.join(os.path.dirname(script_dir), 'keys', 'google_cloud_config.json')
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                
                # 支持两种方式：直接嵌入凭据 或 指定密钥文件路径
                if 'type' in self.config and self.config.get('type') == 'service_account':
                    # 配置文件本身就是服务账户密钥
                    self.config_status_var.set("已配置")
                    self.account_status_var.set("已配置 (直接凭据)")
                else:
                    # 配置文件中指定了密钥文件路径
                    key_path = self.config.get('service_account_key_path', config_file)
                    if not os.path.isabs(key_path):
                        # 相对路径基于配置文件所在目录（项目根目录）
                        key_path = os.path.join(os.path.dirname(script_dir), key_path)
                    
                    if os.path.exists(key_path):
                        self.config_status_var.set("已配置")
                        self.account_status_var.set("已配置")
                        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path
                    else:
                        self.config_status_var.set("配置不完整")
                        self.account_status_var.set(f"密钥文件不存在: {key_path}")
                    
            except json.JSONDecodeError:
                self.config = {}
                self.config_status_var.set("配置错误 (JSON格式无效)")
                self.account_status_var.set("未配置")
            except Exception as e:
                self.config = {}
                self.config_status_var.set(f"配置错误: {e}")
                self.account_status_var.set("未配置")
        else:
            self.config = {}
            self.config_status_var.set(f"未配置 (找不到 {config_file})")
            self.account_status_var.set("未配置")

    def configure_cloud_settings(self):
        """配置Google Cloud Text-to-Speech设置"""
        win = tk.Toplevel(self.master)
        win.title("Google Cloud 配置")
        win.geometry("550x180")

        tk.Label(win, text="服务账户密钥文件:").grid(row=0, column=0, padx=10, pady=15, sticky="e")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_config = os.path.join(os.path.dirname(script_dir), 'keys', 'google_cloud_config.json')
        key_path_var = tk.StringVar(value=self.config.get('service_account_key_path', default_config))
        tk.Entry(win, textvariable=key_path_var, width=40).grid(row=0, column=1, padx=10, pady=15)
        
        def select_key_file():
            path = filedialog.askopenfilename(
                title="选择服务账户密钥文件",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if path:
                key_path_var.set(path)

        tk.Button(win, text="浏览", command=select_key_file).grid(row=0, column=2, padx=10)
        
        # 添加说明文本
        info_text = "提示：密钥文件已统一放置在keys文件夹中。\n如果keys/google_cloud_config.json本身就是服务账户密钥，则使用默认路径即可。"
        tk.Label(win, text=info_text, fg="blue", font=("Arial", 8), justify="left").grid(row=1, column=0, columnspan=3, padx=10, pady=5)

        def save():
            key_path = key_path_var.get().strip()

            if not key_path:
                messagebox.showerror("错误", "请指定服务账户密钥文件路径")
                return
            
            if not os.path.exists(key_path):
                messagebox.showerror("错误", f"文件不存在: {key_path}")
                return

            self.config['service_account_key_path'] = key_path
            self.save_cloud_config()
            
            # 重新加载配置以更新状态
            self.load_cloud_config()
            
            messagebox.showinfo("成功", "Google Cloud配置已保存!")
            win.destroy()

        tk.Button(win, text="保存", command=save).grid(row=2, column=0, columnspan=3, pady=15)

    def save_cloud_config(self):
        """保存Google Cloud配置"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(os.path.dirname(script_dir), 'keys', 'google_cloud_config.json')
            # 确保keys文件夹存在
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")

    def select_output(self):
        path = filedialog.asksaveasfilename(
            title="选择输出文件",
            defaultextension=".mp3",
            filetypes=[("MP3 files", "*.mp3"), ("All files", "*")]
        )
        if path:
            self.output_path_var.set(path)

    def on_model_change(self, event=None):
        """当模型类型改变时更新声音选项"""
        self.update_voice_options()

    def on_language_change(self, event=None):
        """当语言改变时更新声音选项"""
        self.update_voice_options()

    def show_prompt_presets(self):
        """显示预设 Prompt 选项菜单"""
        menu = tk.Menu(self.master, tearoff=0)
        
        presets = {
            "自然朗读": "用自然、流畅的语气朗读",
            "温暖友好": "用温暖、友好的语气讲述",
            "专业播报": "用专业、清晰的语气播报",
            "平静叙述": "用平静、舒缓的语气叙述",
            "兴奋激昂": "用兴奋、充满活力的语气表达",
            "新闻播报": "用新闻播音员的专业语气播报",
            "故事讲述": "用生动、富有表现力的语气讲故事",
            "耳语": "[whispering] 用轻柔的耳语说出",
            "快速": "[extremely fast] 快速说出",
            "清除": ""
        }
        
        for name, prompt in presets.items():
            menu.add_command(
                label=name, 
                command=lambda p=prompt: self.prompt_var.set(p)
            )
        
        # 在按钮下方显示菜单
        menu.post(self.master.winfo_pointerx(), self.master.winfo_pointery())

    def update_voice_options(self):
        """根据选择的语言更新可用的 Gemini-TTS 声音选项"""
        lang_str = self.lang_var.get()
        lang_code = lang_str.split(" ")[0]  # "cmn-CN", "en-US", etc.
        
        # Gemini-TTS 语音列表（通用语音，支持多语言）
        # 基于官方文档: https://cloud.google.com/text-to-speech/docs/gemini-tts#voice_options
        female_voices = ['Kore', 'Aoede', 'Autonoe', 'Callirrhoe', 'Despina', 'Erinome', 'Gacrux', 
                        'Laomedeia', 'Leda', 'Pulcherrima', 'Sulafat', 'Vindemiatrix', 'Zephyr']
        male_voices = ['Charon', 'Achird', 'Algenib', 'Algieba', 'Alnilam', 'Enceladus', 'Fenrir',
                      'Iapetus', 'Orus', 'Puck', 'Rasalgethi', 'Sadachbia', 'Sadaltager', 
                      'Schedar', 'Umbriel', 'Zubenelgenubi']
        
        # 所有可用语音（按字母排序）
        all_voices = sorted(female_voices + male_voices)
        
        # 为中文推荐一些常用语音
        if lang_code == 'cmn-CN':
            # 中文推荐语音在前
            recommended = ['Kore', 'Charon', 'Leda', 'Aoede', 'Puck', 'Zephyr']
            voices = recommended + [v for v in all_voices if v not in recommended]
        else:
            voices = all_voices
        
        # 更新下拉框
        self.voice_combo['values'] = voices
        
        # 如果当前选择的声音不在新列表中，选择第一个
        if self.voice_var.get() not in voices:
            self.voice_var.set(voices[0])

    def get_voice_name_and_lang(self):
        """获取 Gemini-TTS 的模型和语音参数"""
        model_str = self.model_var.get()
        model_name = model_str.split(" ")[0]  # "gemini-2.5-flash-tts", etc.
        
        lang_str = self.lang_var.get()
        lang_code = lang_str.split(" ")[0]  # "cmn-CN", "en-US", etc.
        
        voice_name = self.voice_var.get()  # "Kore", "Charon", etc.
        
        return model_name, voice_name, lang_code

    def start_generation(self):
        input_text = self.input_text.get("1.0", tk.END).strip()
        if not input_text:
            messagebox.showerror("错误", "请输入文本内容")
            return

        if self.config_status_var.get() != "已配置":
            messagebox.showerror("错误", "请先配置Google Cloud API Key")
            return

        self.generate_btn.config(state="disabled")
        self.status_var.set("正在生成...")

        thread = threading.Thread(target=self.generate_speech, args=(input_text,))
        thread.daemon = True
        thread.start()

    def generate_speech(self, input_text):
        try:
            self.status_var.set("正在使用 Gemini-TTS 生成语音...")
            
            output_file = self.output_path_var.get()
            model_name, voice_name, lang_code = self.get_voice_name_and_lang()
            
            # 获取所有参数
            params = {
                'model_name': model_name,
                'voice_name': voice_name,
                'lang_code': lang_code,
                'style_prompt': self.prompt_var.get().strip(),
                'speaking_rate': self.speed_var.get(),
                'pitch': self.pitch_var.get(),
                'volume_gain_db': self.volume_var.get(),
                'audio_format': self.format_var.get()
            }
            
            text_to_speech_with_gemini_tts(input_text, output_file, params)

            self.status_var.set(f"生成完成！文件已保存: {output_file}")
            messagebox.showinfo("成功", f"语音文件已保存到: {output_file}")

        except Exception as e:
            error_msg = f"生成失败: {str(e)}"
            print(f"错误详情: {error_msg}")
            self.status_var.set(error_msg)
            messagebox.showerror("错误", error_msg)
        finally:
            self.generate_btn.config(state="normal")

    # ============ 音频合成视频相关方法 ============

    def select_audio_file(self):
        """选择音频文件"""
        path = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[
                ("音频文件", "*.mp3 *.wav *.m4a *.aac *.ogg *.flac"),
                ("MP3 files", "*.mp3"),
                ("WAV files", "*.wav"),
                ("所有文件", "*.*")
            ]
        )
        if path:
            self.audio_path_var.set(path)
            # 获取音频信息
            try:
                duration = self.get_audio_duration(path)
                filename = os.path.basename(path)
                self.audio_info_var.set(f"文件: {filename} | 时长: {duration:.2f} 秒")
            except Exception as e:
                self.audio_info_var.set(f"文件: {os.path.basename(path)} | 无法读取时长")

    def select_image_file(self):
        """选择图片文件"""
        path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[
                ("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif *.webp"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("PNG files", "*.png"),
                ("所有文件", "*.*")
            ]
        )
        if path:
            self.image_path_var.set(path)
            # 获取图片信息
            try:
                from PIL import Image
                img = Image.open(path)
                filename = os.path.basename(path)
                self.image_info_var.set(f"文件: {filename} | 尺寸: {img.width}x{img.height}")
            except Exception:
                self.image_info_var.set(f"文件: {os.path.basename(path)}")

    def select_video_output(self):
        """选择输出视频文件路径"""
        path = filedialog.asksaveasfilename(
            title="选择输出视频文件",
            defaultextension=".mp4",
            filetypes=[
                ("MP4 files", "*.mp4"),
                ("AVI files", "*.avi"),
                ("MKV files", "*.mkv"),
                ("所有文件", "*.*")
            ]
        )
        if path:
            self.video_output_var.set(path)

    def on_orientation_change(self):
        """当视频方向改变时更新分辨率选项"""
        self.update_resolution_options()

    def update_resolution_options(self):
        """根据视频方向更新分辨率选项"""
        orientation = self.orientation_var.get()
        
        if orientation == "horizontal":
            # 横屏 (16:9)
            resolutions = [
                "1920x1080 (1080p)",
                "1280x720 (720p)",
                "3840x2160 (4K)",
                "2560x1440 (2K)"
            ]
            default = "1920x1080 (1080p)"
        else:
            # 竖屏 (9:16)
            resolutions = [
                "1080x1920 (竖屏1080p)",
                "720x1280 (竖屏720p)",
                "2160x3840 (竖屏4K)",
                "1440x2560 (竖屏2K)"
            ]
            default = "1080x1920 (竖屏1080p)"
        
        self.resolution_combo['values'] = resolutions
        # 如果当前选择不在新列表中，设置为默认值
        current = self.resolution_var.get()
        if current not in resolutions:
            self.resolution_var.set(default)

    def choose_bg_color(self):
        """打开调色板选择背景颜色"""
        from tkinter import colorchooser
        color = colorchooser.askcolor(title="选择背景填充颜色", initialcolor=self.bg_color_var.get())
        if color[1]:  # color[1] 是十六进制颜色值
            self.bg_color_var.set(color[1])
            self.bg_color_preview.config(bg=color[1])

    def choose_watermark_color(self):
        """打开调色板选择水印文字颜色"""
        from tkinter import colorchooser
        color = colorchooser.askcolor(title="选择水印文字颜色", initialcolor=self.watermark_color_var.get())
        if color[1]:  # color[1] 是十六进制颜色值
            self.watermark_color_var.set(color[1])
            self.watermark_color_preview.config(bg=color[1])

    def hex_to_ffmpeg_color(self, hex_color):
        """将十六进制颜色转换为 ffmpeg 可用的格式
        
        Args:
            hex_color: 十六进制颜色，如 "#FF0000" 或 "#F00"
            
        Returns:
            ffmpeg 颜色字符串，格式为 "0xRRGGBB"
        """
        # 移除 # 号
        hex_color = hex_color.lstrip('#')
        
        # 处理简写形式 (如 #F00)
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        
        # 返回 0xRRGGBB 格式
        return f"0x{hex_color.upper()}"

    def build_watermark_filter(self, width, height):
        """构建水印滤镜字符串"""
        watermark_text = self.watermark_text_var.get().strip()
        if not watermark_text:
            return None

        # 获取水印颜色（十六进制格式，如 #FFFFFF）
        hex_color = self.watermark_color_var.get()
        # 将十六进制颜色转换为 ffmpeg 使用的格式（去掉 # 号）
        color = hex_color.lstrip('#')

        # 提取字体
        font_raw = self.watermark_font_var.get()
        # 提取字体文件名（如果包含空格，只取第一部分）
        font = font_raw.split(" ")[0] if " " in font_raw else font_raw
        
        # 字体映射：将字体文件名映射为Windows字体名称
        font_name_mapping = {
            'simhei.ttf': 'Microsoft YaHei',
            'simsun.ttc': 'SimSun',
            'msyh.ttc': 'Microsoft YaHei',
            'simkai.ttf': 'KaiTi',
            'arial.ttf': 'Arial'
        }
        
        # 使用字体名称而不是文件路径
        font_name = font_name_mapping.get(font, 'Microsoft YaHei')

        # 根据分辨率自适应字体大小（基准：1080p = 36px）
        base_size = 36
        base_height = 1080
        font_size = int(base_size * (height / base_height))

        # 获取透明度（转换为0-1范围）
        opacity = self.watermark_opacity_var.get()

        # 获取位置
        position_raw = self.watermark_position_var.get()
        # 从括号中提取英文关键字，例如从 "右上角 (topright)" 提取 "topright"
        if '(' in position_raw and ')' in position_raw:
            position = position_raw.split('(')[1].split(')')[0]
        else:
            position = position_raw

        # 计算边距（自适应分辨率）
        margin = int(30 * (height / base_height))

        # 根据位置设置坐标
        if position == "topright":
            x = f"w-tw-{margin}"
            y = str(margin)
        elif position == "topleft":
            x = str(margin)
            y = str(margin)
        elif position == "bottomright":
            x = f"w-tw-{margin}"
            y = f"h-th-{margin}"
        elif position == "bottomleft":
            x = str(margin)
            y = f"h-th-{margin}"
        else:
            # 默认右上角
            x = f"w-tw-{margin}"
            y = str(margin)

        # 构建drawtext滤镜（参考SubtitleTool.py的实现）
        # 转义特殊字符
        escaped_text = watermark_text.replace(":", "\\:").replace("'", "")
        
        filter_str = (
            f"drawtext=text='{escaped_text}':"
            f"fontcolor={color}@{opacity}:"
            f"fontsize={font_size}:"
            f"font='{font_name}':"
            f"x={x}:y={y}:"
            f"borderw=2:bordercolor=black"
        )

        return filter_str

    def get_audio_duration(self, audio_path):
        """获取音频时长（使用 ffprobe）"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"获取音频时长失败: {e}")
            return 0.0

    def update_resolution_options(self):
        """根据视频方向更新分辨率选项"""
        orientation = self.orientation_var.get()
        
        if orientation == "horizontal":
            # 横屏 (16:9)
            resolutions = [
                "1920x1080 (1080p)",
                "1280x720 (720p)",
                "3840x2160 (4K)",
                "2560x1440 (2K)",
                "自定义"
            ]
            default = "1920x1080 (1080p)"
        else:
            # 竖屏 (9:16)
            resolutions = [
                "1080x1920 (竖屏1080p)",
                "720x1280 (竖屏720p)",
                "2160x3840 (竖屏4K)",
                "1440x2560 (竖屏2K)",
                "自定义"
            ]
            default = "1080x1920 (竖屏1080p)"
        
        self.resolution_combo['values'] = resolutions
        # 如果当前选择不在新列表中，设置为默认值
        if self.resolution_var.get() not in resolutions:
            self.resolution_var.set(default)

    def get_audio_duration(self, audio_path):
        """获取音频时长（使用 ffprobe）"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"获取音频时长失败: {e}")
            return 0.0

    def start_video_generation(self):
        """开始生成视频"""
        audio_path = self.audio_path_var.get()
        image_path = self.image_path_var.get()
        output_path = self.video_output_var.get()

        # 验证输入
        if not audio_path or not os.path.exists(audio_path):
            messagebox.showerror("错误", "请选择有效的音频文件")
            return

        if not image_path or not os.path.exists(image_path):
            messagebox.showerror("错误", "请选择有效的图片文件")
            return

        if not output_path:
            messagebox.showerror("错误", "请指定输出视频文件路径")
            return

        self.generate_video_btn.config(state="disabled")
        self.video_status_var.set("正在生成视频...")

        # 在后台线程中生成视频
        thread = threading.Thread(target=self.generate_video, args=(audio_path, image_path, output_path))
        thread.daemon = True
        thread.start()

    def generate_video(self, audio_path, image_path, output_path):
        """生成视频（后台线程）"""
        try:
            # 解析参数
            resolution_raw = self.resolution_var.get()
            if resolution_raw == "自定义":
                messagebox.showerror("错误", "请选择具体的分辨率，暂不支持自定义")
                self.generate_video_btn.config(state="normal")
                self.video_status_var.set("")
                return
            # 提取分辨率（格式: "1920x1080 (1080p)" 或 "1920x1080"）
            resolution_str = resolution_raw.split(" ")[0]
            width, height = map(int, resolution_str.split('x'))
            fps = int(self.fps_var.get())
            codec_str = self.codec_var.get().split(" ")[0]

            self.video_status_var.set("正在使用 ffmpeg 合成视频...")

            # 获取背景色
            bg_color = self.hex_to_ffmpeg_color(self.bg_color_var.get())

            # 构建视频滤镜链
            # 1. scale: 将图片缩放至适合目标分辨率（保持宽高比）
            # 2. pad: 用背景色填充到目标分辨率
            video_filters = [
                f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={bg_color}"
            ]

            # 如果启用水印，添加水印滤镜
            if self.watermark_enabled_var.get():
                watermark_filter = self.build_watermark_filter(width, height)
                if watermark_filter:
                    video_filters.append(watermark_filter)
            
            # 组合所有滤镜
            filter_complex = ",".join(video_filters)

            # 构建 ffmpeg 命令
            cmd = [
                'ffmpeg',
                '-loop', '1',  # 循环图片
                '-i', image_path,  # 输入图片
                '-i', audio_path,  # 输入音频
                '-vf', filter_complex,  # 视频滤镜
                '-c:v', codec_str,  # 视频编码
                '-c:a', 'aac',  # 音频编码
                '-b:a', '192k',  # 音频比特率
                '-shortest',  # 以最短流为准（音频结束视频就结束）
                '-r', str(fps),  # 帧率
                '-pix_fmt', 'yuv420p',  # 像素格式（兼容性好）
                '-y',  # 覆盖输出文件
                output_path
            ]

            # 执行命令
            print(f"\n{'='*60}")
            print(f"FFmpeg 命令:")
            print(f"{'='*60}")
            for i, arg in enumerate(cmd):
                if arg.startswith('drawtext'):
                    print(f"[{i}] {arg[:100]}...")  # 水印滤镜可能很长，截断显示
                else:
                    print(f"[{i}] {arg}")
            print(f"{'='*60}\n")
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            self.video_status_var.set(f"生成完成！文件已保存: {output_path}")
            messagebox.showinfo("成功", f"视频文件已保存到:\n{output_path}")

        except subprocess.CalledProcessError as e:
            error_msg = f"ffmpeg 错误: {e.stderr}"
            print(f"错误详情: {error_msg}")
            self.video_status_var.set("生成失败")
            messagebox.showerror("错误", f"视频生成失败:\n{error_msg[:200]}")
        except Exception as e:
            error_msg = f"生成失败: {str(e)}"
            print(f"错误详情: {error_msg}")
            self.video_status_var.set("生成失败")
            messagebox.showerror("错误", error_msg)
        finally:
            self.generate_video_btn.config(state="normal")

def text_to_speech_with_gemini_tts(input_text, output_file="output.mp3", params=None):
    """
    使用 Gemini-TTS 生成语音（使用服务账户凭据）
    
    Args:
        input_text: 要转换的文本
        output_file: 输出文件路径
        params: 参数字典，包含 model_name, voice_name, lang_code, style_prompt, speaking_rate, pitch, volume_gain_db, audio_format
    """
    try:
        # 设置默认参数
        if params is None:
            params = {
                'model_name': 'gemini-2.5-flash-tts',
                'voice_name': 'Kore',
                'lang_code': 'cmn-CN',
                'style_prompt': '',
                'speaking_rate': 1.0,
                'pitch': 0.0,
                'volume_gain_db': 0.0,
                'audio_format': 'MP3'
            }
        
        # 读取配置文件 - 从keys文件夹加载
        # 获取当前脚本所在目录的父目录下的keys文件夹
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file = os.path.join(os.path.dirname(script_dir), 'keys', 'google_cloud_config.json')
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件 {config_file} 不存在")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 判断配置文件是服务账户密钥本身还是指向密钥文件
        if 'type' in config and config.get('type') == 'service_account':
            # 配置文件本身就是服务账户密钥
            credentials = service_account.Credentials.from_service_account_info(config)
            client = texttospeech.TextToSpeechClient(credentials=credentials)
        else:
            # 配置文件中指定了密钥文件路径
            key_path = config.get('service_account_key_path', config_file)
            if not os.path.isabs(key_path):
                # 相对路径基于配置文件所在目录（项目根目录）
                key_path = os.path.join(os.path.dirname(script_dir), key_path)
            
            if not os.path.exists(key_path):
                raise FileNotFoundError(f"服务账户密钥文件不存在: {key_path}")
            
            credentials = service_account.Credentials.from_service_account_file(key_path)
            client = texttospeech.TextToSpeechClient(credentials=credentials)

        # Gemini-TTS 输入（支持 text 和 prompt）
        synthesis_input = texttospeech.SynthesisInput(
            text=input_text,
            prompt=params.get('style_prompt', '') if params.get('style_prompt') else None
        )

        # 设置 Gemini-TTS 声音参数
        voice = texttospeech.VoiceSelectionParams(
            language_code=params['lang_code'],
            name=params['voice_name'],
            model_name=params['model_name']  # Gemini-TTS 必须指定 model_name
        )

        # 音频编码格式映射
        audio_encoding_map = {
            'MP3': texttospeech.AudioEncoding.MP3,
            'WAV': texttospeech.AudioEncoding.LINEAR16,
            'OGG_OPUS': texttospeech.AudioEncoding.OGG_OPUS
        }

        # 设置音频配置，包含语速、音调、音量增益
        audio_config = texttospeech.AudioConfig(
            audio_encoding=audio_encoding_map.get(params['audio_format'], texttospeech.AudioEncoding.MP3),
            speaking_rate=params['speaking_rate'],
            pitch=params['pitch'],
            volume_gain_db=params['volume_gain_db']
        )

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        with open(output_file, "wb") as out:
            out.write(response.audio_content)

        print(f"语音文件已保存到: {output_file}")
    
    except Exception as e:
        print(f"生成语音时出错: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    root = tk.Tk()
    app = Text2VideoApp(root)
    root.mainloop()