import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json
import threading
from google.cloud import texttospeech
from google.oauth2 import service_account

class Text2VideoApp:
    def __init__(self, master):
        self.master = master
        master.title("Text to Speech - Google Cloud")
        master.geometry("700x650")
        master.resizable(False, False)

        # Google Cloud 配置状态显示
        tk.Label(master, text="配置状态:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.config_status_var = tk.StringVar(value="未配置")
        tk.Label(master, textvariable=self.config_status_var, fg="red").grid(row=0, column=1, sticky="w")
        tk.Button(master, text="管理配置", command=self.configure_cloud_settings).grid(row=0, column=2, padx=10)

        # API密钥状态
        tk.Label(master, text="API密钥:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.account_status_var = tk.StringVar(value="未配置")
        tk.Label(master, textvariable=self.account_status_var, fg="red").grid(row=1, column=1, sticky="w")

        # 输入文本
        tk.Label(master, text="输入文本:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        self.input_text = tk.Text(master, height=8, width=50, wrap=tk.WORD)
        self.input_text.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0,10))
        # 设置默认文本
        default_text = "欢迎使用文本到语音工具。这是一个测试文本，用于演示如何将文本转换为语音。"
        self.input_text.insert(tk.END, default_text)

        # 输出文件选择
        tk.Label(master, text="输出文件:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
        self.output_path_var = tk.StringVar(value="output.mp3")
        tk.Entry(master, textvariable=self.output_path_var, width=50).grid(row=3, column=1, sticky="w")
        tk.Button(master, text="浏览", command=self.select_output).grid(row=3, column=2, padx=10)

        # 语音模型选择
        tk.Label(master, text="语音模型:").grid(row=4, column=0, padx=10, pady=5, sticky="e")
        self.model_var = tk.StringVar(value="Wavenet")
        model_options = [
            "Standard (标准)",
            "Wavenet (高质量)",
            "Neural2 (神经网络)",
            "Studio (工作室)"
        ]
        self.model_combo = ttk.Combobox(master, textvariable=self.model_var, values=model_options, state="readonly", width=20)
        self.model_combo.grid(row=4, column=1, sticky="w", padx=(0,10))
        self.model_combo.bind('<<ComboboxSelected>>', self.on_model_change)

        # 语言选择
        tk.Label(master, text="语言:").grid(row=5, column=0, padx=10, pady=5, sticky="e")
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
        self.lang_combo = ttk.Combobox(master, textvariable=self.lang_var, values=lang_options, state="readonly", width=20)
        self.lang_combo.grid(row=5, column=1, sticky="w", padx=(0,10))
        self.lang_combo.bind('<<ComboboxSelected>>', self.on_language_change)

        # 声音选择
        tk.Label(master, text="声音:").grid(row=6, column=0, padx=10, pady=5, sticky="e")
        self.voice_var = tk.StringVar(value="A")
        self.voice_combo = ttk.Combobox(master, textvariable=self.voice_var, state="readonly", width=20)
        self.voice_combo.grid(row=6, column=1, sticky="w", padx=(0,10))
        
        # 初始化声音选项
        self.update_voice_options()

        # 语速控制
        tk.Label(master, text="语速:").grid(row=7, column=0, padx=10, pady=5, sticky="e")
        speed_frame = tk.Frame(master)
        speed_frame.grid(row=7, column=1, columnspan=2, sticky="w")
        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_scale = tk.Scale(speed_frame, from_=0.25, to=4.0, resolution=0.05, orient=tk.HORIZONTAL,
                                     variable=self.speed_var, length=200)
        self.speed_scale.pack(side=tk.LEFT)
        self.speed_label = tk.Label(speed_frame, text="1.00x")
        self.speed_label.pack(side=tk.LEFT, padx=5)
        self.speed_var.trace('w', lambda *args: self.speed_label.config(text=f"{self.speed_var.get():.2f}x"))

        # 音调控制
        tk.Label(master, text="音调:").grid(row=8, column=0, padx=10, pady=5, sticky="e")
        pitch_frame = tk.Frame(master)
        pitch_frame.grid(row=8, column=1, columnspan=2, sticky="w")
        self.pitch_var = tk.DoubleVar(value=0.0)
        self.pitch_scale = tk.Scale(pitch_frame, from_=-20.0, to=20.0, resolution=0.5, orient=tk.HORIZONTAL,
                                     variable=self.pitch_var, length=200)
        self.pitch_scale.pack(side=tk.LEFT)
        self.pitch_label = tk.Label(pitch_frame, text="0.0")
        self.pitch_label.pack(side=tk.LEFT, padx=5)
        self.pitch_var.trace('w', lambda *args: self.pitch_label.config(text=f"{self.pitch_var.get():.1f}"))

        # 音量增益控制
        tk.Label(master, text="音量增益:").grid(row=9, column=0, padx=10, pady=5, sticky="e")
        volume_frame = tk.Frame(master)
        volume_frame.grid(row=9, column=1, columnspan=2, sticky="w")
        self.volume_var = tk.DoubleVar(value=0.0)
        self.volume_scale = tk.Scale(volume_frame, from_=-96.0, to=16.0, resolution=1.0, orient=tk.HORIZONTAL,
                                      variable=self.volume_var, length=200)
        self.volume_scale.pack(side=tk.LEFT)
        self.volume_label = tk.Label(volume_frame, text="0.0 dB")
        self.volume_label.pack(side=tk.LEFT, padx=5)
        self.volume_var.trace('w', lambda *args: self.volume_label.config(text=f"{self.volume_var.get():.1f} dB"))

        # 音频格式选择
        tk.Label(master, text="音频格式:").grid(row=10, column=0, padx=10, pady=5, sticky="e")
        self.format_var = tk.StringVar(value="MP3")
        format_options = ["MP3", "WAV", "OGG_OPUS"]
        self.format_combo = ttk.Combobox(master, textvariable=self.format_var, values=format_options, state="readonly", width=15)
        self.format_combo.grid(row=10, column=1, sticky="w", padx=(0,10))

        # 生成按钮
        self.generate_btn = tk.Button(master, text="生成语音", command=self.start_generation, width=20)
        self.generate_btn.grid(row=11, column=1, pady=20)

        # 进度/提示
        self.status_var = tk.StringVar()
        tk.Label(master, textvariable=self.status_var, fg="blue").grid(row=12, column=0, columnspan=3, pady=10)

        # 加载现有配置
        self.config = {}
        self.load_cloud_config()

    def load_cloud_config(self):
        """加载Google Cloud配置，使用服务账户密钥文件"""
        config_file = os.path.join('..', 'keys', 'google_cloud_config.json')
        
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
                        key_path = os.path.abspath(key_path)
                    
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
        key_path_var = tk.StringVar(value=self.config.get('service_account_key_path', os.path.join('..', 'keys', 'google_cloud_config.json')))
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
            config_file = os.path.join('..', 'keys', 'google_cloud_config.json')
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

    def update_voice_options(self):
        """根据选择的模型和语言更新可用的声音选项"""
        model_str = self.model_var.get()
        model_type = model_str.split(" ")[0]  # "Standard", "Wavenet", "Neural2", "Studio"
        
        lang_str = self.lang_var.get()
        lang_code = lang_str.split(" ")[0]  # "cmn-CN", "en-US", etc.
        
        # 根据不同的语言和模型类型，提供不同的声音选项
        # 基于Google Cloud TTS官方文档: https://cloud.google.com/text-to-speech/docs/voices
        voice_map = {
            'cmn-CN': {'Standard': ['A', 'B', 'C', 'D'], 
                      'Wavenet': ['A', 'B', 'C', 'D'], 
                      'Neural2': [],  # cmn-CN没有Neural2
                      'Studio': []},  # cmn-CN没有Studio
            'en-US': {'Standard': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'], 
                     'Wavenet': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
                     'Neural2': ['A', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
                     'Studio': ['O', 'Q']},
            'en-GB': {'Standard': ['A', 'B', 'C', 'D', 'F', 'N', 'O'], 
                     'Wavenet': ['A', 'B', 'C', 'D', 'F', 'N', 'O'],
                     'Neural2': ['A', 'B', 'C', 'D', 'F', 'N', 'O'], 
                     'Studio': ['B', 'C']},
            'ja-JP': {'Standard': ['A', 'B', 'C', 'D'], 
                     'Wavenet': ['A', 'B', 'C', 'D'],
                     'Neural2': ['B', 'C', 'D'], 
                     'Studio': []},
            'ko-KR': {'Standard': ['A', 'B', 'C', 'D'], 
                     'Wavenet': ['A', 'B', 'C', 'D'],
                     'Neural2': ['A', 'B', 'C'], 
                     'Studio': []},
            'fr-FR': {'Standard': ['F', 'G'], 
                     'Wavenet': ['F', 'G'],
                     'Neural2': ['F', 'G'], 
                     'Studio': ['A', 'D']},
            'de-DE': {'Standard': ['G', 'H'], 
                     'Wavenet': ['G', 'H'],
                     'Neural2': ['G', 'H'], 
                     'Studio': ['B', 'C']},
            'es-ES': {'Standard': ['E', 'F', 'G', 'H'], 
                     'Wavenet': ['E', 'F', 'G', 'H'],
                     'Neural2': ['E', 'F', 'G', 'H'], 
                     'Studio': ['C', 'F']}
        }
        
        # 获取可用的声音列表
        voices = voice_map.get(lang_code, {}).get(model_type, ['A'])
        
        if not voices:
            voices = ['A']  # 默认
        
        # 更新下拉框
        self.voice_combo['values'] = voices
        
        # 如果当前选择的声音不在新列表中，选择第一个
        if self.voice_var.get() not in voices:
            self.voice_var.set(voices[0])

    def get_voice_name_and_lang(self):
        """根据选择的模型、语言和声音构建完整的声音名称"""
        model_str = self.model_var.get()
        model_type = model_str.split(" ")[0]  # "Standard", "Wavenet", "Neural2", "Studio"
        
        lang_str = self.lang_var.get()
        lang_code = lang_str.split(" ")[0]  # "cmn-CN", "en-US", etc.
        
        voice_letter = self.voice_var.get()  # "A", "B", "C", etc.
        
        # 构建完整的声音名称，例如: "cmn-CN-Wavenet-A" 或 "en-US-Neural2-C"
        voice_name = f"{lang_code}-{model_type}-{voice_letter}"
        
        return voice_name, lang_code

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
            self.status_var.set("正在使用Google Cloud Text-to-Speech生成语音...")
            
            output_file = self.output_path_var.get()
            voice_name, lang_code = self.get_voice_name_and_lang()
            
            # 获取所有参数
            params = {
                'voice_name': voice_name,
                'lang_code': lang_code,
                'speaking_rate': self.speed_var.get(),
                'pitch': self.pitch_var.get(),
                'volume_gain_db': self.volume_var.get(),
                'audio_format': self.format_var.get()
            }
            
            text_to_speech_with_google_cloud(input_text, output_file, params)

            self.status_var.set(f"生成完成！文件已保存: {output_file}")
            messagebox.showinfo("成功", f"语音文件已保存到: {output_file}")

        except Exception as e:
            error_msg = f"生成失败: {str(e)}"
            print(f"错误详情: {error_msg}")
            self.status_var.set(error_msg)
            messagebox.showerror("错误", error_msg)
        finally:
            self.generate_btn.config(state="normal")

def text_to_speech_with_google_cloud(input_text, output_file="output.mp3", params=None):
    """
    使用Google Cloud Text-to-Speech生成语音（使用服务账户凭据）
    
    Args:
        input_text: 要转换的文本
        output_file: 输出文件路径
        params: 参数字典，包含 voice_name, lang_code, speaking_rate, pitch, volume_gain_db, audio_format
    """
    try:
        # 设置默认参数
        if params is None:
            params = {
                'voice_name': 'cmn-CN-Wavenet-A',
                'lang_code': 'cmn-CN',
                'speaking_rate': 1.0,
                'pitch': 0.0,
                'volume_gain_db': 0.0,
                'audio_format': 'MP3'
            }
        
        # 读取配置文件 - 从keys文件夹加载
        # 获取当前脚本所在目录的父目录下的keys文件夹
        config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'keys', 'google_cloud_config.json')
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
                key_path = os.path.abspath(key_path)
            
            if not os.path.exists(key_path):
                raise FileNotFoundError(f"服务账户密钥文件不存在: {key_path}")
            
            credentials = service_account.Credentials.from_service_account_file(key_path)
            client = texttospeech.TextToSpeechClient(credentials=credentials)

        synthesis_input = texttospeech.SynthesisInput(text=input_text)

        # 设置声音参数
        voice = texttospeech.VoiceSelectionParams(
            language_code=params['lang_code'],
            name=params['voice_name']
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