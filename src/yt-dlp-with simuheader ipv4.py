import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import yt_dlp
import os
import threading
import subprocess
from urllib.parse import urlparse

class YouTubeDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader")
        self.root.geometry("1200x650")  # Wider window for horizontal layout
        
        # Initialize yt-dlp
        self.ydl_opts = {}
        self.video_list = []  # List of videos from URLs/playlists
        self.selected_videos = []  # Selected videos for download
        
        # Network configuration
        self.network_speed = "fast"  # fast, medium, slow
        self.force_ipv4_var = tk.BooleanVar(value=True)
        
        # Progress update throttling - 避免事件队列堆积
        self.last_progress_update = {}  # {video_title: last_update_time}
        self.progress_update_interval = 0.5  # 最小更新间隔（秒）
        
        # Create GUI elements
        self.create_widgets()
        
    def create_widgets(self):
        # Create main frames for left and right panels
        left_frame = tk.Frame(self.root, padx=10, pady=10)
        left_frame.grid(row=0, column=0, sticky="nsew")
        
        right_frame = tk.Frame(self.root, padx=10, pady=10)
        right_frame.grid(row=0, column=1, sticky="nsew")
        
        # Configure grid weights
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Left Panel - Input and Selection
        # URL Input (multi-line for multiple URLs)
        tk.Label(left_frame, text="Video URLs (one per line):", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0,5))
        self.url_text = tk.Text(left_frame, height=4, width=50, wrap=tk.WORD)
        self.url_text.pack(fill=tk.X, pady=(0,10))
        
        # Get Video List Button
        self.get_list_btn = tk.Button(left_frame, text="Get Video List", command=self.get_video_list, 
                                    bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.get_list_btn.pack(fill=tk.X, pady=(0,10))
        
        # Video List Display with Checkboxes
        tk.Label(left_frame, text="Available Videos:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0,5))
        self.list_frame = tk.Frame(left_frame)
        self.list_frame.pack(fill=tk.BOTH, expand=True, pady=(0,10))
        
        # Scrollbar for list
        self.scrollbar = tk.Scrollbar(self.list_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.video_listbox = tk.Listbox(self.list_frame, selectmode=tk.MULTIPLE, height=12, width=50, 
                                       yscrollcommand=self.scrollbar.set, font=("Arial", 9))
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.video_listbox.yview)
        
        # Select All / Deselect All Buttons
        select_frame = tk.Frame(left_frame)
        select_frame.pack(pady=(0,10))
        tk.Button(select_frame, text="Select All", command=self.select_all, width=12).grid(row=0, column=0, padx=(0,5))
        tk.Button(select_frame, text="Deselect All", command=self.deselect_all, width=12).grid(row=0, column=1)
        
        # Quality and Options
        options_frame = tk.Frame(left_frame)
        options_frame.pack(fill=tk.X, pady=(0,10))
        
        # Video Quality
        tk.Label(options_frame, text="Video Quality:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", pady=(0,5))
        self.quality_combo = ttk.Combobox(options_frame, values=["best", "1080p", "720p", "480p", "360p"], 
                                         state="readonly", width=15)
        self.quality_combo.current(0)
        self.quality_combo.grid(row=1, column=0, sticky="w", pady=(0,10))
        
        # MP3 Checkbox
        self.mp3_var = tk.BooleanVar()
        tk.Checkbutton(options_frame, text="Extract MP3", variable=self.mp3_var, font=("Arial", 9)).grid(row=2, column=0, sticky="w")
        
        # Network Speed
        tk.Label(options_frame, text="Network Speed:", font=("Arial", 9, "bold")).grid(row=3, column=0, sticky="w", pady=(10,5))
        self.network_combo = ttk.Combobox(options_frame, values=["Fast (30MB chunks)", "Medium (15MB chunks)", "Slow (5MB chunks)"], 
                                         state="readonly", width=20)
        self.network_combo.current(0)
        self.network_combo.grid(row=4, column=0, sticky="w", pady=(0,5))
        tk.Label(options_frame, text="(选择网络速度以优化下载)", font=("Arial", 7), fg="gray").grid(row=5, column=0, sticky="w")

        # IPv4 Option
        tk.Checkbutton(options_frame, text="Force IPv4 (-4)", variable=self.force_ipv4_var, font=("Arial", 9)).grid(row=6, column=0, sticky="w", pady=(8,0))
        
        # Right Panel - Output and Download
        # Output Directory
        tk.Label(right_frame, text="Download Settings", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0,10))
        
        output_frame = tk.Frame(right_frame)
        output_frame.pack(fill=tk.X, pady=(0,20))
        
        tk.Label(output_frame, text="Save to:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0,5))
        self.dir_entry = tk.Entry(output_frame, width=40, font=("Arial", 9))
        self.dir_entry.grid(row=1, column=0, sticky="ew", pady=(0,5))
        tk.Button(output_frame, text="Browse", command=self.browse_directory, width=10).grid(row=1, column=1, padx=(5,0))
        
        output_frame.grid_columnconfigure(0, weight=1)
        
        # Download Button
        self.download_btn = tk.Button(right_frame, text="Start Download", command=self.start_download, 
                                    state="disabled", bg="#2196F3", fg="white", font=("Arial", 12, "bold"), 
                                    height=2)
        self.download_btn.pack(fill=tk.X, pady=(0,20))
        
        # Progress/Status Display
        tk.Label(right_frame, text="Download Status", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0,5))
        self.status_text = tk.Text(right_frame, height=15, width=50, wrap=tk.WORD, font=("Arial", 9))
        self.status_text.pack(fill=tk.BOTH, expand=True)
        self.status_text.config(state="disabled")
        
    def log(self, message):
        self.status_text.config(state="normal")
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state="disabled")
        # 移除 root.update() - 让事件循环自然处理，避免递归
        
    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)
            
    def select_all(self):
        self.video_listbox.select_set(0, tk.END)
        
    def deselect_all(self):
        self.video_listbox.selection_clear(0, tk.END)
        
    def get_video_list(self):
        urls = self.url_text.get("1.0", tk.END).strip().split('\n')
        urls = [url.strip() for url in urls if url.strip()]
        force_ipv4 = self.force_ipv4_var.get()
        if not urls:
            messagebox.showerror("Error", "Please enter at least one URL")
            return
            
        self.get_list_btn.config(state="disabled")
        self.log("Fetching video list...")
        self.video_list = []
        self.video_listbox.delete(0, tk.END)
        
        def fetch_list():
            try:
                # First try with extract_flat=False for full metadata
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': False,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                    'referer': 'https://www.youtube.com/',
                    'extract_flat': False,
                    # 网络和缓冲区优化
                    'buffersize': 131072,  # 128KB内存缓冲区
                    'http_chunk_size': 10485760,  # 10MB HTTP块大小
                    'retries': 10,  # 下载重试次数
                    'fragment_retries': 10,  # 片段重试次数
                    'file_access_retries': 5,  # 文件访问重试
                    'socket_timeout': 30,  # Socket超时30秒
                }

                if force_ipv4:
                    ydl_opts['source_address'] = '0.0.0.0'
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    for url in urls:
                        try:
                            info = ydl.extract_info(url, download=False)
                            if 'entries' in info:
                                # It's a playlist
                                for entry in info['entries']:
                                    if entry:
                                        self.video_list.append({
                                            'title': entry.get('title', 'Unknown Title'),
                                            'url': entry.get('webpage_url', entry.get('url', url)),
                                            'duration': entry.get('duration', 0),
                                            'uploader': entry.get('uploader', info.get('uploader', 'Unknown')),
                                            'playlist': info.get('title', 'Unknown Playlist')
                                        })
                            else:
                                # Single video
                                self.video_list.append({
                                    'title': info.get('title', 'Unknown Title'),
                                    'url': info.get('webpage_url', url),
                                    'duration': info.get('duration', 0),
                                    'uploader': info.get('uploader', 'Unknown'),
                                    'playlist': None
                                })
                        except Exception as e:
                            # Fallback to extract_flat=True
                            self.log(f"Fallback for URL: {url}")
                            ydl_flat_opts = ydl_opts.copy()
                            ydl_flat_opts['extract_flat'] = True
                            with yt_dlp.YoutubeDL(ydl_flat_opts) as ydl_flat:
                                info = ydl_flat.extract_info(url, download=False)
                                if 'entries' in info:
                                    # It's a playlist
                                    for entry in info['entries']:
                                        if entry:
                                            self.video_list.append({
                                                'title': entry.get('title', f"Video {entry.get('id', 'Unknown')}"),
                                                'url': entry.get('url', url),
                                                'duration': 0,  # Not available in flat mode
                                                'uploader': info.get('uploader', 'Unknown'),
                                                'playlist': info.get('title', 'Unknown Playlist')
                                            })
                                else:
                                    # Single video
                                    self.video_list.append({
                                        'title': info.get('title', 'Unknown Title'),
                                        'url': info.get('webpage_url', url),
                                        'duration': info.get('duration', 0),
                                        'uploader': info.get('uploader', 'Unknown'),
                                        'playlist': None
                                    })
                
                self.root.after(0, self.update_video_listbox)
            except Exception as e:
                error_message = str(e)
                self.root.after(0, lambda em=error_message: messagebox.showerror("Error", f"Failed to fetch video list: {em}"))
                self.root.after(0, lambda em=error_message: self.log(f"Error: {em}"))
                self.root.after(0, lambda: self.get_list_btn.config(state="normal"))
                
        threading.Thread(target=fetch_list, daemon=True).start()
            
    def update_video_listbox(self):
        for video in self.video_list:
            duration = int(video['duration']) if video['duration'] else 0
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration > 0 else "Unknown"
            if video.get('playlist'):
                display_text = f"[{video['playlist']}] {video['title']} - {duration_str} - {video['uploader']}"
            else:
                display_text = f"{video['title']} - {duration_str} - {video['uploader']}"
            self.video_listbox.insert(tk.END, display_text)
        self.get_list_btn.config(state="normal")
        if self.video_list:
            self.download_btn.config(state="normal")
        self.log(f"Found {len(self.video_list)} videos")
        
    def start_download(self):
        selected_indices = self.video_listbox.curselection()
        if not selected_indices:
            messagebox.showerror("Error", "Please select at least one video to download")
            return
            
        output_dir = self.dir_entry.get().strip()
        if not output_dir:
            messagebox.showerror("Error", "Please select an output directory")
            return
            
        if not os.path.exists(output_dir):
            messagebox.showerror("Error", "Invalid output directory")
            return
            
        self.selected_videos = [self.video_list[i] for i in selected_indices]
        quality = self.quality_combo.get()
        force_ipv4 = self.force_ipv4_var.get()
        
        self.download_btn.config(state="disabled")
        self.get_list_btn.config(state="disabled")
        self.log(f"Starting download of {len(self.selected_videos)} videos...")
        self.log("Initializing download thread...")
        
        def download():
            try:
                self.root.after(0, lambda: self.log("Download thread started successfully"))
                self.root.after(0, lambda: self.log("Checking FFmpeg installation..."))
                # Check FFmpeg
                try:
                    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=10)
                    self.root.after(0, lambda: self.log("FFmpeg check passed"))
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
                    error_msg = f"FFmpeg not found or not working: {str(e)}"
                    self.root.after(0, lambda em=error_msg: messagebox.showerror("Error", "FFmpeg not found. Install FFmpeg for video processing."))
                    self.root.after(0, lambda em=error_msg: self.log(em))
                    self.root.after(0, lambda: self.download_btn.config(state="normal"))
                    self.root.after(0, lambda: self.get_list_btn.config(state="normal"))
                    return
                
                for i, video in enumerate(self.selected_videos):
                    video_title = video['title']
                    idx = i + 1
                    total = len(self.selected_videos)
                    self.root.after(0, lambda vt=video_title, n=idx, t=total: self.log(f"Starting download {n}/{t}: {vt}"))
                    
                    # Map quality to format - 修复格式选择逻辑
                    # 使用 bestvideo+bestaudio 确保获取最高质量的音视频流
                    if quality == "best":
                        format_str = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]"
                    elif quality == "1080p":
                        format_str = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]"
                    elif quality == "720p":
                        format_str = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]"
                    elif quality == "480p":
                        format_str = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]"
                    elif quality == "360p":
                        format_str = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]"
                    else:
                        format_str = "bestvideo+bestaudio/best"
                    
                    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
                    
                    # 根据网络速度选择HTTP块大小和并发设置
                    network_choice = self.network_combo.get()
                    if "Fast" in network_choice:
                        http_chunk = 31457280  # 30MB
                        buffersize = 16777216  # 16MB 内存缓冲区
                        concurrent = 8         # 并发下载8个片段
                    elif "Medium" in network_choice:
                        http_chunk = 15728640  # 15MB
                        buffersize = 8388608   # 8MB 内存缓冲区
                        concurrent = 5         # 并发下载5个片段
                    else:  # Slow
                        http_chunk = 5242880   # 5MB
                        buffersize = 4194304   # 4MB 内存缓冲区
                        concurrent = 3         # 并发下载3个片段
                    
                    self.root.after(0, lambda hc=http_chunk//1048576, bs=buffersize//1048576, c=concurrent: 
                                   self.log(f"Using {hc}MB chunks, {bs}MB buffer, {c} concurrent downloads"))
                    
                    ydl_opts = {
                        'format': format_str,
                        'outtmpl': output_template,
                        'merge_output_format': 'mp4',
                        
                        # FFmpeg后处理优化参数 - 音视频都不重编码以提速
                        'postprocessor_args': {
                            'ffmpeg': [
                                '-c:v', 'copy',              # 视频流直接复制
                                '-c:a', 'copy',              # 音频流也直接复制，不重编码
                                '-threads', '0',             # 使用所有CPU线程
                                '-movflags', '+faststart',   # 优化MP4结构
                            ]
                        },
                        
                        # 网络和缓冲区优化
                        'http_chunk_size': http_chunk,       # 动态HTTP块大小
                        'buffersize': buffersize,            # 内存缓冲区
                        'retries': 10,                       # 下载重试次数
                        'fragment_retries': 10,              # 片段重试次数
                        'file_access_retries': 5,            # 文件访问重试
                        'skip_unavailable_fragments': True,  # 跳过不可用片段
                        'socket_timeout': 30,                # Socket超时
                        
                        # 并发下载优化
                        'concurrent_fragment_downloads': concurrent,  # 动态并发数
                        
                        # 其他优化
                        'progress_hooks': [self.create_progress_hook(video)],
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                        'referer': 'https://www.youtube.com/',
                        'quiet': False,
                        'no_warnings': False,
                        'noprogress': False,
                        'ignoreerrors': False,               # 不忽略错误
                    }

                    if force_ipv4:
                        ydl_opts['source_address'] = '0.0.0.0'

                    self.root.after(0, lambda enabled=force_ipv4: self.log(f"Force IPv4: {'ON' if enabled else 'OFF'}"))
                    
                    try:
                        self.root.after(0, lambda vt=video_title: self.log(f"Initializing yt-dlp for: {vt}"))
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            self.root.after(0, lambda vt=video_title: self.log(f"Extracting info for: {vt}"))
                            info = ydl.extract_info(video['url'], download=True)
                            video_file = ydl.prepare_filename(info)
                        
                        self.root.after(0, lambda vf=video_file, vt=video_title: self.log(f"Downloaded: {vt} -> {vf}"))
                        
                        # Extract MP3 if selected
                        if self.mp3_var.get():
                            self.root.after(0, lambda vt=video_title: self.log(f"Extracting MP3 for: {vt}"))
                            mp3_file = os.path.splitext(video_file)[0] + '.mp3'
                            try:
                                # 使用优化的FFmpeg参数提取MP3
                                subprocess.run([
                                    'ffmpeg', '-y',
                                    '-i', video_file,
                                    '-vn',                      # 不处理视频流
                                    '-acodec', 'libmp3lame',    # 使用高质量MP3编码器
                                    '-b:a', '192k',             # 音频码率
                                    '-ar', '44100',             # 采样率44.1kHz
                                    '-threads', '0',            # 使用所有CPU线程
                                    mp3_file
                                ], check=True, capture_output=True, timeout=600)  # 10分钟超时，足够长视频
                                self.root.after(0, lambda mf=mp3_file: self.log(f"MP3 saved: {mf}"))
                            except subprocess.TimeoutExpired:
                                error_msg = f"MP3 extraction timeout for {video_title} (超过10分钟)"
                                self.root.after(0, lambda em=error_msg: self.log(em))
                            except subprocess.CalledProcessError as e:
                                error_msg = f"MP3 extraction failed for {video_title}: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)}"
                                self.root.after(0, lambda em=error_msg: self.log(em))
                    
                    except Exception as video_error:
                        error_msg = f"Failed to download {video_title}: {str(video_error)}"
                        self.root.after(0, lambda em=error_msg: self.log(em))
                        continue  # Continue with next video
                
                self.root.after(0, lambda: self.log("All downloads completed!"))
                self.root.after(0, lambda: messagebox.showinfo("Success", "All downloads completed!"))
                
            except Exception as e:
                error_msg = f"Download process failed: {str(e)}"
                self.root.after(0, lambda em=error_msg: messagebox.showerror("Error", em))
                self.root.after(0, lambda em=error_msg: self.log(em))
                
            finally:
                self.root.after(0, lambda: self.download_btn.config(state="normal"))
                self.root.after(0, lambda: self.get_list_btn.config(state="normal"))
        
        # Start the download thread
        self.log("Starting download thread...")
        threading.Thread(target=download, daemon=True).start()
        
    def create_progress_hook(self, video):
        """Create a progress hook function for a specific video"""
        video_title = video['title']  # 提前捕获标题
        import time
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                # 节流机制：限制进度更新频率
                current_time = time.time()
                last_update = self.last_progress_update.get(video_title, 0)
                
                # 只有距离上次更新超过指定间隔才更新进度
                if current_time - last_update >= self.progress_update_interval:
                    self.last_progress_update[video_title] = current_time
                    progress = d.get('_percent_str', '0%').replace('%', '')
                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    # 使用try-except保护，避免事件队列问题
                    try:
                        self.root.after_idle(lambda vt=video_title, p=progress, s=speed, e=eta: 
                                           self.log(f"{vt} - {p}% | Speed: {s} | ETA: {e}"))
                    except:
                        pass  # 如果事件队列满了，跳过这次更新
                        
            elif d['status'] == 'finished':
                # 完成消息必须显示
                try:
                    self.root.after_idle(lambda vt=video_title: self.log(f"{vt} - Download finished, processing..."))
                except:
                    pass
                # 清理进度记录
                if video_title in self.last_progress_update:
                    del self.last_progress_update[video_title]
                    
            elif 'error' in d['status'].lower():
                error_msg = d.get('info_dict', {}).get('error', 'Unknown error')
                try:
                    self.root.after_idle(lambda vt=video_title, em=error_msg: self.log(f"{vt} - Error: {em}"))
                except:
                    pass
        return progress_hook

if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloader(root)
    root.mainloop()